# 庫存管理系統（AILearn Inventory）

以 BMAD 方法（PRD → 切片 → 實作 → 審查）建置的多倉庫進銷存系統。

- **需求來源**：`庫存管理課題.pptx`（14 頁課程課題）
- **PRD**：`_bmad-output/planning-artifacts/prds/prd-庫存管理系統-2026-10-21/prd.md`（v3，32 條 FR、9 條使用者旅程、11 條成功指標）
- **技術選型與資料模型**：同目錄 `addendum.md`
- **實作規格**：`_bmad-output/implementation-artifacts/spec-mvp-slice-1-登入權限與庫存查詢.md`

## 技術棧

| 層次 | 選型 |
| --- | --- |
| 前端 | React 18 + Vite + react-router |
| 後端 | Python Flask（app factory）、Flask-SQLAlchemy、Flask-Migrate（Alembic） |
| 資料庫 | PostgreSQL（資料庫名稱 `AILearn`）、psycopg 3 |
| 認證 | Session cookie + bcrypt；角色權限在伺服器端檢查 |

## 目錄結構

```
backend/
  app/
    __init__.py        create_app()
    config.py          環境變數設定（DATABASE_URL / SECRET_KEY / SEED_PASSWORD）
    extensions.py      db、migrate、cors 實例
    models.py          全部資料模型（改動須同步產生 migration）
    security.py        密碼雜湊、登入鎖定、稽核紀錄寫入
    auth.py            /api/auth/* 與 require_roles 裝飾器
    api/masterdata.py  商品／供應商／客戶／倉庫／位置 API
    api/stock.py       庫存查詢 API（在手量／可用量／在途量）
    seed.py            種子資料（flask seed）
    timeutil.py        UTC 時間工具
  migrations/          Flask-Migrate 產生的遷移檔
  tests/               pytest 驗收測試（以 SQLite 記憶體庫執行，不需 PostgreSQL）
frontend/
  src/                 React 應用（登入、庫存查詢、主檔瀏覽）
```

## 環境需求

- Node.js 20.12+、Python 3.10+（本專案使用 3.12 venv）、PostgreSQL 14+

## 首次設定

### 1. 後端

```powershell
cd backend
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
Copy-Item .env.example .env
# 編輯 .env，填入 DATABASE_URL 密碼、SECRET_KEY、SEED_PASSWORD
```

`SECRET_KEY` 產生方式：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. 建立資料庫與角色（需 postgres 超級使用者權限）

```powershell
psql -U postgres -c "CREATE ROLE ailearn_app LOGIN PASSWORD '你的密碼';"
psql -U postgres -c "CREATE DATABASE AILearn OWNER ailearn_app ENCODING 'UTF8';"
```

### 3. 建立資料表並寫入種子資料

```powershell
cd backend
$env:FLASK_APP = "wsgi:app"
.venv/Scripts/python.exe -m flask db upgrade
.venv/Scripts/python.exe -m flask seed
```

種子帳號（密碼取自 `.env` 的 `SEED_PASSWORD`）：

| 帳號 | 姓名 | 角色 |
| --- | --- | --- |
| `admin` | 系統管理員 | 管理員 |
| `warehouse` | 倉管阿哲 | 倉管 |
| `purchasing` | 採購大明 | 採購 |
| `sales` | 業務小美 | 銷售 |
| `accounting` | 會計小陳 | 會計 |

> 種子帳號皆標記為「首次登入須修改密碼」。

### 4. 啟動

後端（127.0.0.1:5000）：

```powershell
cd backend
.venv/Scripts/python.exe -m flask --app wsgi run --port 5000
```

前端（127.0.0.1:5173，開發模式以 proxy 轉發 `/api`）：

```powershell
cd frontend
npm install
npm run dev
```

開啟 http://127.0.0.1:5173

## 測試

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q
```

測試以 SQLite 記憶體資料庫執行，**不需 PostgreSQL**，涵蓋切片 1 的驗收條件（AC-1 ~ AC-9）。

## 資安原則（PRD §3、§4.9、addendum §3）

- 密碼以 bcrypt 單向雜湊儲存；**任何明文密碼不得進入版控、投影片、對話紀錄或日誌**。
- `.env` 已被 `.gitignore` 排除；連線字串以環境變數注入。
- 連線字串使用**最小權限的專用角色**（`ailearn_app`），不使用 `postgres` 超級使用者帳號。
- 角色權限一律在**伺服器端**檢查；前端隱藏按鈕不算通過。
- 操作紀錄（`audit_logs`）只增不改，無刪除 API。

## 目前交付範圍（切片 1）

**已完成**：帳密登入／登出、五角色權限矩陣（伺服器端）、連續失敗鎖定、稽核紀錄、商品／供應商／客戶／倉庫／位置主檔、庫存查詢（在手量／可用量／在途量、模糊搜尋、展開明細）、種子資料、驗收測試。

**尚未開放**（後續切片）：入庫、領用出庫、跨倉調貨、盤點、調整與報廢、銷貨單與毛利、寄貨單、採購與水位警示、報表與匯出、列印。
