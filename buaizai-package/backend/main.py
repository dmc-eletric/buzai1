"""
部材管理システム — FastAPI Backend
=====================================
Deploy: Render.com  (Web Service + PostgreSQL)
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from database import engine
import models
from auth import hash_password
from database import SessionLocal
from routers import auth, users, items, history, upload

# ── Auto-create tables ────────────────────────────
models.Base.metadata.create_all(bind=engine)


# ── Seed default admin if no users exist ─────────
def _seed_admin():
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            admin_user = models.User(
                username=os.getenv("DEFAULT_ADMIN_ID", "admin"),
                display_name="システム管理者",
                hashed_password=hash_password(os.getenv("DEFAULT_ADMIN_PW", "admin1234")),
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            print("[seed] デフォルト管理者を作成しました → admin / admin1234")
            print("[seed] ⚠ ログイン後すぐにパスワードを変更してください")
    finally:
        db.close()


# ── Scheduled auto-cleanup ────────────────────────
scheduler = AsyncIOScheduler()

def _scheduled_cleanup():
    days = int(os.getenv("AUTO_CLEANUP_DAYS", "0"))
    if days <= 0:
        return  # disabled
    from datetime import datetime, timezone, timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        items_to_delete = (
            db.query(models.Item)
              .filter(models.Item.status == "USED")
              .filter(models.Item.used_at < cutoff)
              .all()
        )
        import storage as stor
        for item in items_to_delete:
            if item.photo_url:
                stor.delete_photo(item.photo_url)
            db.delete(item)
        db.commit()
        print(f"[cleanup] {len(items_to_delete)}件のUSED部材を自動削除しました (cutoff={days}日)")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_admin()
    scheduler.add_job(_scheduled_cleanup, "cron", hour=2, minute=0)  # runs at 02:00 UTC daily
    scheduler.start()
    yield
    scheduler.shutdown()


# ── App ───────────────────────────────────────────
app = FastAPI(
    title="部材管理システム API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow GitHub Pages and local dev
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(items.router)
app.include_router(history.router)
app.include_router(upload.router)

# Serve uploaded photos when using local storage
uploads_path = Path("./uploads")
uploads_path.mkdir(exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


# ── Health check ──────────────────────────────────
@app.get("/", tags=["health"])
def root():
    return {"status": "部材管理システム API running", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"ok": True}
