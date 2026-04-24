"""
Photo upload endpoint.

Cloudinaryに転送するだけなので、PIL/Pillowによるリサイズは不要。
Cloudinary側のtransformationで自動最適化しています（storage.py参照）。
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from schemas import UploadResponse
from auth import get_current_user
import models
import storage

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_FILE_SIZE  = 15 * 1024 * 1024   # 15 MB（Cloudinaryの無料プラン上限に余裕を持たせる）
ALLOWED_TYPES  = {
    "image/jpeg", "image/jpg", "image/png",
    "image/webp", "image/heic", "image/heif",
}


@router.post("/photo", response_model=UploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    _: models.User = Depends(get_current_user),
):
    # MIMEタイプ検証
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES and not content_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail="画像ファイルのみアップロードできます（JPEG / PNG / WebP / HEIC）",
        )

    data = await file.read()

    # サイズ検証
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"ファイルサイズが大きすぎます（最大 {MAX_FILE_SIZE // 1024 // 1024} MB）",
        )

    import io
    filename = (file.filename or "photo.jpg").split("/")[-1]

    try:
        url = storage.upload_photo(io.BytesIO(data), filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cloudinaryへのアップロードに失敗しました: {e}")

    return UploadResponse(url=url, filename=filename)
