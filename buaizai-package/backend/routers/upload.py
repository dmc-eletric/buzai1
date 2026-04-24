import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from PIL import Image

from schemas import UploadResponse
from auth import get_current_user
import models
import storage

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_DIMENSION  = 1920               # resize if larger


def _compress(data: bytes, content_type: str) -> bytes:
    """Resize and compress image to keep storage small."""
    try:
        img = Image.open(io.BytesIO(data))
        # Convert HEIC / RGBA / palette to RGB
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        # Auto-rotate based on EXIF
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        # Downscale if too large
        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue()
    except Exception:
        return data  # fallback: upload as-is


@router.post("/photo", response_model=UploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    _: models.User = Depends(get_current_user),
):
    # Validate MIME type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES and not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="画像ファイルのみアップロードできます")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="ファイルサイズが大きすぎます（最大10MB）")

    # Compress
    compressed = _compress(data, content_type)
    filename   = (file.filename or "photo.jpg").split("/")[-1]

    url = storage.upload_photo(io.BytesIO(compressed), filename)
    return UploadResponse(url=url, filename=filename)
