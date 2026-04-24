"""
部材管理システム — FastAPI Backend
=====================================
Deploy: Render.com  (Web Service + PostgreSQL)
"""
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

from database import engine, SessionLocal
import models
from auth import hash_password
from routers import auth, users, items, history, upload


# ── テーブル作成 ──────────────────────────────────
def _create_tables():
    try:
        models.Base.metadata.create_all(bind=engine)
        print("[startup] テーブル作成OK")
    except Exception as e:
        print(f"[startup] テーブル作成エラー: {e}")
        traceback.print_exc()
        raise  # テーブル作れないなら起動を止める


# ── デフォルト管理者を作成 ────────────────────────
def _seed_admin():
    db = SessionLocal()
    try:
        count = db.query(models.User).count()
        print(f"[seed] 現在のユーザー数: {count}")

        if count == 0:
            admin_id = os.getenv("DEFAULT_ADMIN_ID", "admin").strip()
            admin_pw = os.getenv("DEFAULT_ADMIN_PW", "admin1234").strip()

            if not admin_id or not admin_pw:
                print("[seed] ⚠ DEFAULT_ADMIN_ID / DEFAULT_ADMIN_PW が未設定のためスキップ")
                return

            admin_user = models.User(
                username=admin_id,
                display_name="システム管理者",
                hashed_password=hash_password(admin_pw),
                is_admin=True,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"[seed] ✅ 管理者を作成しました: {admin_id}")
            print("[seed] ⚠ ログイン後すぐにパスワードを変更してください")
        else:
            print("[seed] ユーザーが存在するためスキップ")

    except Exception as e:
        print(f"[seed] ❌ エラー: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


# ── 自動クリーンアップ ────────────────────────────
scheduler = AsyncIOScheduler()

def _scheduled_cleanup():
    days = int(os.getenv("AUTO_CLEANUP_DAYS", "0"))
    if days <= 0:
        return
    from datetime import datetime, timezone, timedelta
    import storage as stor
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        targets = (
            db.query(models.Item)
              .filter(models.Item.status == "USED")
              .filter(models.Item.used_at < cutoff)
              .all()
        )
        for item in targets:
            if item.photo_url:
                stor.delete_photo(item.photo_url)
            db.delete(item)
        db.commit()
        print(f"[cleanup] {len(targets)}件削除 (>{days}日)")
    except Exception as e:
        print(f"[cleanup] エラー: {e}")
        db.rollback()
    finally:
        db.close()


# ── Lifespan ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時に必ず実行
    _create_tables()
    _seed_admin()
    scheduler.add_job(_scheduled_cleanup, "cron", hour=2, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()


# ── App ───────────────────────────────────────────
app = FastAPI(
    title="部材管理システム API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
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

# ローカルストレージ用 static ファイル配信
uploads_path = Path("./uploads")
uploads_path.mkdir(exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


# ── Health & Debug endpoints ──────────────────────
@app.get("/", tags=["health"])
def root():
    return {"status": "部材管理システム API running", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"ok": True}


@app.get("/debug/seed", tags=["debug"])
def debug_seed():
    """
    管理者アカウントが存在しない場合に手動で再作成するエンドポイント。
    ログインできない場合にブラウザから叩いて確認・修復できます。
    本番稼働が安定したらこのエンドポイントを削除してください。
    """
    db = SessionLocal()
    try:
        count = db.query(models.User).count()
        users_list = [
            {"username": u.username, "is_admin": u.is_admin, "is_active": u.is_active}
            for u in db.query(models.User).all()
        ]

        if count == 0:
            admin_id = os.getenv("DEFAULT_ADMIN_ID", "admin").strip()
            admin_pw = os.getenv("DEFAULT_ADMIN_PW", "admin1234").strip()
            admin_user = models.User(
                username=admin_id,
                display_name="システム管理者",
                hashed_password=hash_password(admin_pw),
                is_admin=True,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            return {
                "action": "created",
                "username": admin_id,
                "message": f"管理者 '{admin_id}' を作成しました。DEFAULT_ADMIN_PWのパスワードでログインしてください。",
            }
        else:
            return {
                "action": "skipped",
                "user_count": count,
                "users": users_list,
                "message": "ユーザーが存在するためスキップしました",
            }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


@app.post("/debug/reset-admin-password", tags=["debug"])
def debug_reset_admin(body: dict):
    """
    管理者パスワードを強制リセットする。
    body: {"username": "admin", "new_password": "newpass123", "secret": "ENV_SECRET_KEY値"}
    secretにSECRET_KEYの値を渡すことで不正利用を防ぎます。
    """
    secret = os.getenv("SECRET_KEY", "")
    if not secret or body.get("secret") != secret:
        return {"error": "secretが一致しません"}

    username = body.get("username", "").strip()
    new_pw   = body.get("new_password", "").strip()
    if not username or not new_pw:
        return {"error": "usernameとnew_passwordが必要です"}
    if len(new_pw) < 6:
        return {"error": "パスワードは6文字以上必要です"}

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            return {"error": f"ユーザー '{username}' が見つかりません"}
        user.hashed_password = hash_password(new_pw)
        user.is_active = True
        db.commit()
        return {"ok": True, "message": f"'{username}' のパスワードをリセットしました"}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
