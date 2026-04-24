# 部材管理システム — デプロイガイド

## システム構成

```
GitHub Pages  →  index.html (フロントエンド)
Render.com    →  FastAPI    (バックエンド API)
Render.com    →  PostgreSQL (データベース)
Render.com /  →  ローカルストレージ (写真)
Cloudflare R2    または R2 (写真推奨)
```

---

## 1. バックエンド — Render へのデプロイ

### 手順

1. `buaizai-backend/` フォルダをGitHubリポジトリにプッシュ

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/buaizai-backend.git
git push -u origin main
```

2. [render.com](https://render.com) でアカウント作成 → New → PostgreSQL
   - Name: `buaizai-db`
   - Plan: Free (開発) / Starter 以上 (本番)
   - 作成後、**Internal Database URL** をコピー

3. render.com → New → Web Service → GitHubリポジトリを選択
   - **Name**: `buaizai-api`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. Environment Variables を設定:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Render PostgreSQL の Internal URL |
| `SECRET_KEY` | ランダム文字列 (32文字以上) |
| `DEFAULT_ADMIN_ID` | `admin` |
| `DEFAULT_ADMIN_PW` | 安全なパスワード |
| `ALLOWED_ORIGINS` | `https://yourname.github.io` |
| `STORAGE_BACKEND` | `local` または `r2` |
| `LOCAL_BASE_URL` | `https://buaizai-api.onrender.com` |
| `TOKEN_EXPIRE_HOURS` | `12` |
| `AUTO_CLEANUP_DAYS` | `30` (0=無効) |

5. Deploy → URLをメモ (例: `https://buaizai-api.onrender.com`)

---

## 2. 写真ストレージ (推奨: Cloudflare R2)

### なぜR2か
- Render の無料プランはディスクが揮発性 → 再デプロイで写真が消える
- R2 は 10GB まで無料、永続ストレージ

### R2 設定手順

1. [Cloudflare](https://dash.cloudflare.com) → R2 → Create Bucket
   - Bucket名: `buaizai-photos`
   - Public アクセスを有効化

2. R2 → Manage API Tokens → Create Token (Object Read & Write)

3. Render の環境変数に追加:

| Key | Value |
|-----|-------|
| `STORAGE_BACKEND` | `r2` |
| `R2_ACCOUNT_ID` | CloudflareアカウントID |
| `R2_ACCESS_KEY_ID` | R2 Access Key |
| `R2_SECRET_ACCESS_KEY` | R2 Secret |
| `R2_BUCKET_NAME` | `buaizai-photos` |
| `R2_PUBLIC_URL` | `https://pub-XXXX.r2.dev` |

---

## 3. フロントエンド — GitHub Pages

1. GitHubで新しいリポジトリ作成 (例: `buaizai-app`)

2. `index.html` をリポジトリのルートに配置

3. `index.html` の API URL を変更:
```javascript
const API = "https://buaizai-api.onrender.com";  // ← Render URL に変更
```

4. Settings → Pages → Source: `main` branch → Save

5. URL: `https://yourname.github.io/buaizai-app`

---

## 4. 初期ログイン

1. `https://yourname.github.io/buaizai-app` にアクセス
2. ID: `admin` / PW: `admin1234` でログイン
3. 管理設定 → パスワード変更 (必須)
4. 管理設定 → ユーザー追加 で現場スタッフのアカウントを発行

---

## 5. ネットワークプリンター連携 (オプション)

小型ラベルプリンター (Brother, DYMO, ZebraなどZPL/ESC-POS対応) と連携する場合:

1. プリンター用ミドルウェアをPCまたはRaspberry Piで起動
   - 例: `python printer_middleware.py`
   - このミドルウェアは `POST /print` でJSONを受け取りZPLに変換して印刷

2. 管理設定 → プリンターURL に `http://192.168.1.100:8888/print` を入力

3. URLが未設定の場合はブラウザの印刷ダイアログ (Web Print) にフォールバック

### ミドルウェアサンプル (printer_middleware.py)

```python
from flask import Flask, request
import socket, json

app = Flask(__name__)
PRINTER_IP   = "192.168.1.200"
PRINTER_PORT = 9100

@app.route("/print", methods=["POST"])
def print_label():
    data = request.json
    code = data.get("code", "")
    name = data.get("name", "")
    zpl = f"""
^XA
^FO50,30^BQN,2,5^FDQA,{code}^FS
^FO50,200^A0N,28,28^FD{code}^FS
^FO50,235^A0N,22,22^FD{name[:20]}^FS
^XZ
"""
    try:
        s = socket.socket()
        s.connect((PRINTER_IP, PRINTER_PORT))
        s.send(zpl.encode())
        s.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888)
```

---

## 6. 内部管理コード規則

```
YYYYMMDD - MODEL - NNN
20250421 - MA9500 - 001
```

- `YYYYMMDD` : 登録日 (JST)
- `MODEL`    : 機種名の英数字 (最大8文字)
- `NNN`      : 当日・同機種の連番 (3桁ゼロ埋め)

---

## 7. API エンドポイント一覧

| Method | Path | 説明 |
|--------|------|------|
| POST | `/auth/login` | ログイン → JWT発行 |
| GET | `/users/` | ユーザー一覧 (Admin) |
| POST | `/users/` | ユーザー追加 (Admin) |
| DELETE | `/users/{username}` | ユーザー削除 (Admin) |
| GET | `/items/` | 部材一覧 (フィルタ対応) |
| POST | `/items/` | 部材登録 |
| GET | `/items/stats` | ダッシュボード統計 |
| GET | `/items/next-seq` | 次の連番取得 |
| GET | `/items/by-code/{code}` | コードで部材検索 |
| GET | `/items/{id}` | 部材詳細 |
| PUT | `/items/{id}/use` | USE済みに変更 |
| DELETE | `/items/{id}` | 部材削除 |
| DELETE | `/items/cleanup` | USED部材一括削除 |
| GET | `/history/` | 操作履歴 |
| POST | `/history/` | 履歴記録 |
| POST | `/upload/photo` | 写真アップロード |
| GET | `/health` | ヘルスチェック |

---

## 8. フォルダ構成

```
buaizai-backend/
├── main.py              # FastAPI アプリ本体
├── database.py          # DB接続設定
├── models.py            # SQLAlchemy モデル
├── schemas.py           # Pydantic スキーマ
├── auth.py              # JWT認証
├── storage.py           # 写真ストレージ抽象層
├── routers/
│   ├── auth.py          # ログインエンドポイント
│   ├── users.py         # ユーザー管理
│   ├── items.py         # 部材CRUD
│   ├── history.py       # 操作履歴
│   └── upload.py        # 写真アップロード
├── requirements.txt
├── render.yaml          # Renderデプロイ設定
├── alembic.ini          # DBマイグレーション設定
└── .env.example         # 環境変数テンプレート

buaizai-frontend/
└── index.html           # 全フロントエンド (1ファイル)
```
