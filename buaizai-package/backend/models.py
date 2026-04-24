from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True, index=True)
    username       = Column(String(120), unique=True, nullable=False, index=True)
    display_name   = Column(String(100), nullable=False, default="")
    hashed_password= Column(String, nullable=False)
    is_admin       = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime(timezone=True), default=utcnow)


class Item(Base):
    """
    部材 (buaizai) — a tracked component/part.

    Status lifecycle:
        READY  →  USED
    """
    __tablename__ = "items"

    id             = Column(Integer, primary_key=True, index=True)
    internal_code  = Column(String(80), unique=True, nullable=False, index=True)
    ext_code       = Column(String(80), nullable=True, index=True)
    model          = Column(String(80), nullable=False, index=True)    # 機種名
    serial         = Column(String(80), nullable=False)                # シリアル番号
    product        = Column(String(200), nullable=False)               # 製品名
    requester      = Column(String(100), nullable=True)                # 依頼者
    note           = Column(Text, nullable=True)                       # 備考
    photo_url      = Column(String, nullable=True)
    status         = Column(String(10), nullable=False, default="READY", index=True)  # READY | USED
    operator       = Column(String(100), nullable=False)               # 登録者
    created_at     = Column(DateTime(timezone=True), default=utcnow, index=True)
    used_by        = Column(String(100), nullable=True)
    used_at        = Column(DateTime(timezone=True), nullable=True)


class HistoryLog(Base):
    """
    Audit log for every ADD / USE / PRINT / DELETE action.
    """
    __tablename__ = "history_logs"

    id             = Column(Integer, primary_key=True, index=True)
    item_id        = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    internal_code  = Column(String(80), nullable=True, index=True)
    action         = Column(String(20), nullable=False, index=True)   # ADD | USE | PRINT | DELETE
    operator       = Column(String(100), nullable=False)
    note           = Column(Text, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=utcnow, index=True)
