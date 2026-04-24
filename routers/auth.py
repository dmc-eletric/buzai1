from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import LoginRequest, TokenResponse
from auth import verify_password, create_access_token
import models

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.username == req.username,
        models.User.is_active == True,
    ).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="IDまたはパスワードが正しくありません")

    token = create_access_token({"sub": user.username})
    return TokenResponse(
        access_token=token,
        is_admin=user.is_admin,
        username=user.username,
        display_name=user.display_name or user.username,
    )
