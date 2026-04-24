from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import HistoryCreate, HistoryOut
from auth import get_current_user
import models

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=list[HistoryOut])
def list_history(
    q:      str | None = Query(None),
    action: str | None = Query(None),
    limit:  int = Query(300, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    query = db.query(models.HistoryLog)
    if action:
        query = query.filter(models.HistoryLog.action == action)
    if q:
        like = f"%{q}%"
        query = query.filter(
            models.HistoryLog.internal_code.ilike(like) |
            models.HistoryLog.operator.ilike(like)
        )
    return (
        query.order_by(models.HistoryLog.created_at.desc())
             .offset(offset).limit(limit).all()
    )


@router.post("/", response_model=HistoryOut, status_code=201)
def create_log(
    req: HistoryCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    log = models.HistoryLog(**req.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
