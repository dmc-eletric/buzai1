import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import LoginRequest, TokenResponse
from auth import verify_password, create_access_token
import models

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    print(f"[login] 試行: username='{req.username}'")

    try:
        user = db.query(models.User).filter(
            models.User.username == req.username,
        ).first()
    except Exception as e:
        print(f"[login] DBエラー: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="データベースエラーが発生しました")

    if user is None:
        print(f"[login] ❌ ユーザーが存在しない: '{req.username}'")
        raise HTTPException(status_code=401, detail="IDまたはパスワードが正しくありません")

    if not user.is_active:
        print(f"[login] ❌ アカウント無効: '{req.username}'")
        raise HTTPException(status_code=401, detail="IDまたはパスワードが正しくありません")

    pw_ok = verify_password(req.password, user.hashed_password)
    if not pw_ok:
        print(f"[login] ❌ パスワード不一致: '{req.username}'")
        raise HTTPException(status_code=401, detail="IDまたはパスワードが正しくありません")

    print(f"[login] ✅ ログイン成功: '{req.username}' (is_admin={user.is_admin})")
    token = create_access_token({"sub": user.username})
    return TokenResponse(
        access_token=token,
        is_admin=user.is_admin,
        username=user.username,
        display_name=user.display_name or user.username,
    )
