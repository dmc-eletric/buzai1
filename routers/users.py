from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import UserCreate, UserOut
from auth import hash_password, require_admin, get_current_user
import models

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    return db.query(models.User).order_by(models.User.created_at).all()


@router.post("/", response_model=UserOut, status_code=201)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    existing = db.query(models.User).filter(models.User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="このユーザーIDはすでに使用されています")
    user = models.User(
        username=req.username,
        display_name=req.display_name or req.username,
        hashed_password=hash_password(req.password),
        is_admin=req.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{username}", status_code=204)
def delete_user(
    username: str,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_admin),
):
    if username == current.username:
        raise HTTPException(status_code=400, detail="自分自身を削除することはできません")
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    db.delete(user)
    db.commit()


@router.put("/me/password", status_code=200)
def change_password(
    body: dict,
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    from auth import verify_password as vp
    old_pw = body.get("old_password", "")
    new_pw = body.get("new_password", "")
    if not vp(old_pw, current.hashed_password):
        raise HTTPException(status_code=400, detail="現在のパスワードが正しくありません")
    if len(new_pw) < 6:
        raise HTTPException(status_code=400, detail="パスワードは6文字以上必要です")
    current.hashed_password = hash_password(new_pw)
    db.commit()
    return {"ok": True}
