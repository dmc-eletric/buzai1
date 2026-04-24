"""
Storage layer — Cloudinary backend
====================================
必要な環境変数:
  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET

写真は buaizai/photos/ フォルダに保存されます。
削除時は public_id から自動判別して削除します。
"""
import os
import re

import cloudinary
import cloudinary.uploader

# ── Cloudinary 初期設定 ───────────────────────────
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    api_key    = os.getenv("CLOUDINARY_API_KEY",    ""),
    api_secret = os.getenv("CLOUDINARY_API_SECRET", ""),
    secure     = True,   # 常にHTTPS
)

FOLDER = "buaizai/photos"


def upload_photo(file_obj, original_filename: str) -> str:
    """
    バイナリファイルをCloudinaryにアップロードして公開URLを返す。

    Parameters
    ----------
    file_obj : file-like object (BinaryIO / BytesIO)
    original_filename : str  元のファイル名（拡張子判定のみ使用）

    Returns
    -------
    str  Cloudinaryの公開URL (https://res.cloudinary.com/...)
    """
    result = cloudinary.uploader.upload(
        file_obj,
        folder         = FOLDER,
        resource_type  = "image",
        # 横幅1920px超は自動縮小、品質・形式を自動最適化
        transformation = [
            {
                "width": 1920,
                "crop": "limit",
                "quality": "auto:good",
                "fetch_format": "auto",
            }
        ],
        overwrite = False,
    )
    return result["secure_url"]


def delete_photo(url: str) -> None:
    """
    CloudinaryのURLからpublic_idを逆算して削除する。
    エラーは無視（ベストエフォート）。

    URL例:
      https://res.cloudinary.com/CLOUD/image/upload/v123456/buaizai/photos/abcdef.jpg
    → public_id = buaizai/photos/abcdef
    """
    if not url:
        return
    try:
        # /upload/ 以降、バージョン番号を除いた部分から拡張子を除く
        match = re.search(r"/upload/(?:v\d+/)?(.+)\.[a-zA-Z0-9]+$", url)
        if not match:
            return
        public_id = match.group(1)
        cloudinary.uploader.destroy(public_id, resource_type="image")
    except Exception:
        pass  # 削除失敗はベストエフォートで無視
