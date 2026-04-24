from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# ── AUTH ─────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool
    username: str
    display_name: str


# ── USER ─────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── ITEM ─────────────────────────────────────────
class ItemCreate(BaseModel):
    internal_code: str
    model: str
    serial: str
    product: str
    ext_code: Optional[str] = None
    requester: Optional[str] = None
    note: Optional[str] = None
    photo_url: Optional[str] = None
    operator: str
    status: str = "READY"


class ItemOut(BaseModel):
    id: int
    internal_code: str
    ext_code: Optional[str]
    model: str
    serial: str
    product: str
    requester: Optional[str]
    note: Optional[str]
    photo_url: Optional[str]
    status: str
    operator: str
    created_at: datetime
    used_by: Optional[str]
    used_at: Optional[datetime]
    model_config = {"from_attributes": True}


class UseRequest(BaseModel):
    used_by: str


class NextSeqResponse(BaseModel):
    seq: int
    date: str
    model: str


# ── STATS ─────────────────────────────────────────
class ModelCount(BaseModel):
    model: str
    count: int


class UserCount(BaseModel):
    operator: str
    count: int


class StatsResponse(BaseModel):
    ready: int
    used_today: int
    used_all: int
    total: int
    by_model: list[ModelCount]
    by_user_today: list[UserCount]


# ── HISTORY ──────────────────────────────────────
class HistoryCreate(BaseModel):
    item_id: Optional[int] = None
    internal_code: Optional[str] = None
    action: str          # ADD | USE | PRINT | DELETE
    operator: str
    note: Optional[str] = None


class HistoryOut(BaseModel):
    id: int
    item_id: Optional[int]
    internal_code: Optional[str]
    action: str
    operator: str
    note: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── UPLOAD ────────────────────────────────────────
class UploadResponse(BaseModel):
    url: str
    filename: str


# ── CLEANUP ───────────────────────────────────────
class CleanupResponse(BaseModel):
    deleted: int
    days: int
