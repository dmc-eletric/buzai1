from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timezone, timedelta

from database import get_db
from schemas import (
    ItemCreate, ItemOut, UseRequest,
    NextSeqResponse, StatsResponse, CleanupResponse,
    ModelCount, UserCount,
)
from auth import get_current_user
import models
import storage

router = APIRouter(prefix="/items", tags=["items"])


# ── Helper ────────────────────────────────────────
def _get_item_or_404(item_id: int, db: Session) -> models.Item:
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="部材が見つかりません")
    return item


# ── CRUD ──────────────────────────────────────────
@router.get("/", response_model=list[ItemOut])
def list_items(
    status: str | None = Query(None),
    model:  str | None = Query(None),
    operator: str | None = Query(None),
    date:   str | None = Query(None, description="YYYY-MM-DD"),
    q:      str | None = Query(None, description="全文検索"),
    limit:  int = Query(500, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    query = db.query(models.Item)
    if status:
        query = query.filter(models.Item.status == status)
    if model:
        query = query.filter(models.Item.model == model)
    if operator:
        query = query.filter(models.Item.operator == operator)
    if date:
        query = query.filter(cast(models.Item.created_at, Date) == date)
    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Item.internal_code.ilike(like) |
            models.Item.product.ilike(like) |
            models.Item.model.ilike(like) |
            models.Item.serial.ilike(like) |
            models.Item.ext_code.ilike(like) |
            models.Item.operator.ilike(like) |
            models.Item.requester.ilike(like)
        )
    return (
        query.order_by(models.Item.created_at.desc())
             .offset(offset).limit(limit).all()
    )


@router.post("/", response_model=ItemOut, status_code=201)
def create_item(
    req: ItemCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    if db.query(models.Item).filter(models.Item.internal_code == req.internal_code).first():
        raise HTTPException(status_code=409, detail="管理コードが重複しています")
    item = models.Item(**req.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    today = datetime.now(timezone.utc).date()

    ready     = db.query(models.Item).filter(models.Item.status == "READY").count()
    used_all  = db.query(models.Item).filter(models.Item.status == "USED").count()
    total     = db.query(models.Item).count()
    used_today = (
        db.query(models.Item)
          .filter(models.Item.status == "USED")
          .filter(cast(models.Item.used_at, Date) == today)
          .count()
    )

    # By model (READY only)
    by_model_rows = (
        db.query(models.Item.model, func.count(models.Item.id))
          .filter(models.Item.status == "READY")
          .group_by(models.Item.model)
          .order_by(func.count(models.Item.id).desc())
          .all()
    )
    by_model = [ModelCount(model=r[0], count=r[1]) for r in by_model_rows]

    # By operator today (ADD)
    by_user_rows = (
        db.query(models.Item.operator, func.count(models.Item.id))
          .filter(cast(models.Item.created_at, Date) == today)
          .group_by(models.Item.operator)
          .order_by(func.count(models.Item.id).desc())
          .all()
    )
    by_user = [UserCount(operator=r[0], count=r[1]) for r in by_user_rows]

    return StatsResponse(
        ready=ready,
        used_today=used_today,
        used_all=used_all,
        total=total,
        by_model=by_model,
        by_user_today=by_user,
    )


@router.get("/next-seq", response_model=NextSeqResponse)
def next_seq(
    date:  str = Query(..., description="YYYYMMDD"),
    model: str = Query(..., description="機種コード"),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Return next available sequence number for internal_code generation."""
    prefix = f"{date}-{model}-"
    count = (
        db.query(models.Item)
          .filter(models.Item.internal_code.like(f"{prefix}%"))
          .count()
    )
    return NextSeqResponse(seq=count + 1, date=date, model=model)


@router.get("/by-code/{code}", response_model=ItemOut)
def get_by_code(
    code: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    item = (
        db.query(models.Item)
          .filter(
              (models.Item.internal_code == code) |
              (models.Item.ext_code == code)
          ).first()
    )
    if not item:
        raise HTTPException(status_code=404, detail=f"コード '{code}' の部材が見つかりません")
    return item


@router.get("/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _get_item_or_404(item_id, db)


@router.put("/{item_id}/use", response_model=ItemOut)
def mark_used(
    item_id: int,
    req: UseRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    if item.status == "USED":
        raise HTTPException(status_code=400, detail="この部材はすでにUSED状態です")
    item.status  = "USED"
    item.used_by = req.used_by
    item.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    if item.photo_url:
        storage.delete_photo(item.photo_url)
    db.delete(item)
    db.commit()


@router.delete("/cleanup", response_model=CleanupResponse)
def cleanup_used(
    days: int = Query(30, ge=1, le=3650),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Delete USED items older than `days` days and their photos."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = (
        db.query(models.Item)
          .filter(models.Item.status == "USED")
          .filter(models.Item.used_at < cutoff)
          .all()
    )
    deleted = 0
    for item in items:
        if item.photo_url:
            storage.delete_photo(item.photo_url)
        db.delete(item)
        deleted += 1
    db.commit()
    return CleanupResponse(deleted=deleted, days=days)
