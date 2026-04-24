"""
Storage abstraction layer.

Priority:
  1. Cloudflare R2 (via boto3 S3-compatible API) — set R2_* env vars
  2. AWS S3 — set AWS_* env vars
  3. Local filesystem fallback — files saved under ./uploads/

Set STORAGE_BACKEND=r2 | s3 | local in .env
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import BinaryIO

BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

# ── Cloudflare R2 / AWS S3 ───────────────────────
R2_ACCOUNT_ID      = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID   = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME     = os.getenv("R2_BUCKET_NAME", "buaizai-photos")
R2_PUBLIC_URL      = os.getenv("R2_PUBLIC_URL", "")   # e.g. https://pub.r2.dev/xxx

AWS_ACCESS_KEY_ID  = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION         = os.getenv("AWS_REGION", "ap-northeast-1")
AWS_BUCKET_NAME    = os.getenv("AWS_BUCKET_NAME", "buaizai-photos")
AWS_PUBLIC_URL     = os.getenv("AWS_PUBLIC_URL", "")  # CloudFront or direct S3 URL

# ── Local ────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
LOCAL_BASE_URL = os.getenv("LOCAL_BASE_URL", "")  # e.g. https://your-render.com


def _get_s3_client(backend: str):
    import boto3
    if backend == "r2":
        endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        ), R2_BUCKET_NAME, R2_PUBLIC_URL
    else:
        return boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        ), AWS_BUCKET_NAME, AWS_PUBLIC_URL


def upload_photo(file_obj: BinaryIO, original_filename: str) -> str:
    """Upload photo and return public URL."""
    ext = Path(original_filename).suffix.lower() or ".jpg"
    filename = f"photos/{uuid.uuid4().hex}{ext}"

    if BACKEND in ("r2", "s3"):
        client, bucket, base_url = _get_s3_client(BACKEND)
        content_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        client.upload_fileobj(
            file_obj,
            bucket,
            filename,
            ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
        )
        if base_url:
            return f"{base_url.rstrip('/')}/{filename}"
        region = AWS_REGION if BACKEND == "s3" else "auto"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"

    # Local fallback
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    local_path = UPLOAD_DIR / filename.replace("/", "_")
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file_obj, f)
    base = LOCAL_BASE_URL.rstrip("/") if LOCAL_BASE_URL else ""
    return f"{base}/static/uploads/{local_path.name}"


def delete_photo(url: str) -> None:
    """Best-effort delete — ignores errors."""
    if not url:
        return
    try:
        if BACKEND in ("r2", "s3"):
            client, bucket, base_url = _get_s3_client(BACKEND)
            key = url.split(base_url.rstrip("/") + "/")[-1]
            client.delete_object(Bucket=bucket, Key=key)
        else:
            filename = url.split("/")[-1]
            path = UPLOAD_DIR / filename
            if path.exists():
                path.unlink()
    except Exception:
        pass
