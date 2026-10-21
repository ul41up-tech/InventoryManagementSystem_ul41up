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
- 選用：`uv`（建立 venv 與安裝套件 faster）、`ruff`（靜態檢查）

## 每日開機：怎麼開起來

**電腦重開後，資料都還在**（PostgreSQL 服務設為自動啟動，資料庫與 `backend\.env` 都在磁碟上），
只有伺服器程序需要重啟。

### 快速：雙擊腳本

| 雙擊 | 開啟網址 | 用途 |
| --- | --- | --- |
| `start-dev.bat` | http://localhost:5173 | 開發模式：檢查 PG → 啟後端 → 啟前端 → 等就緒 → 自動開瀏覽器 |
| `start-backend.bat` | http://127.0.0.1:5000 | 單一服務：只啟後端，Flask 同時託管打包好的前端與 API（會自動 `npm run build`） |
| `stop-dev.bat` | — | 停止開發模式的後端與前端 |
| `stop-backend.bat` | — | 停止單一服務模式的後端 |

純 API 模式（不開瀏覽器）：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1 -ApiOnly
```

### 手動操作

**方式 A：只啟動後端（單一服務，網頁＋API 同一個埠）**

先打包前端（第一次或前端改完之後）：

```powershell
cd frontend
npm install          # 只有第一次需要
npm run build        # 產生 frontend\dist
```

啟動後端：

```powershell
cd backend
.venv\Scripts\python.exe -m flask --app wsgi run --port 5000
```

開瀏覽器到 **http://127.0.0.1:5000**。

> 前端改動後要重新 `npm run build` 才會反映到這個模式。

**方式 B：開發模式（前後端分離，改前端會熱更新）**

開兩個終端機：

```powershell
# 終端機 1：後端 API
cd backend
.venv\Scripts\python.exe -m flask --app wsgi run --port 5000
```

```powershell
# 終端機 2：前端（Vite）
cd frontend
npm run dev
```

開瀏覽器到 **http://localhost:5173**（Vite 只綁 `localhost`，不要用 `127.0.0.1:5173`）。
需要讓同網段其他裝置連入時用 `npm run dev -- --host`。

**停止**

在啟動伺服器的終端機按 `Ctrl+C`。若是背景程序：

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 5173 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

執行紀錄（若改用背景執行）在 `logs/`。

## 首次設定

### 1. 後端

```powershell
cd backend
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
Copy-Item .env.example .env
# 編輯 .env，填入 DATABASE_URL 密碼、SECRET_KEY、SEED_PASSWORD
```

macOS / Linux：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

`SECRET_KEY` 產生方式：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> `SECRET_KEY` 未設定時應用**拒絕啟動**（不使用公開已知的預設值）；`SEED_PASSWORD` 未設定時 `flask seed` 會拒絕執行。

### 2. 建立資料庫與角色（需 postgres 超級使用者權限）

**方式 A（建議）：用密碼檔讓腳本代勞**

把 PostgreSQL `postgres` 超級使用者密碼貼到 `backend/db_password.txt` 最後一行（取代「在此貼上密碼」），然後執行：

```powershell
backend\.venv\Scripts\python.exe backend\tools\setup_database.py
```

腳本會直接讀檔建立角色 `ailearn_app`、資料庫 `AILearn`、寫入 `backend/.env`（隨機密鑰），
再執行 `flask db upgrade` 與 `flask seed`。**密碼全程不經對話、不進版控**（`db_password.txt` 已被 `.gitignore` 排除）。
完成後可把該檔內容清空——superuser 密碼之後不再需要。

**方式 B：自己下指令**

```powershell
psql -U postgres -c "CREATE ROLE ailearn_app LOGIN PASSWORD '你的密碼';"
psql -U postgres -c "CREATE DATABASE AILearn OWNER ailearn_app ENCODING 'UTF8';"
```

接著手動把連線字串寫進 `backend/.env`。

### 3. 建立資料表並寫入種子資料

```powershell
cd backend
$env:FLASK_APP = "wsgi:app"
.venv/Scripts/python.exe -m flask db upgrade
.venv/Scripts/python.exe -m flask seed
```

> 初始 migration（`backend/migrations/versions/0001_initial_schema.py`）已隨程式碼產出並提交，由
> `backend/tools/generate_initial_migration.py` 以 SQLAlchemy metadata 產生（不需資料庫連線）。
> **若 `app/models.py` 的表結構有變更，必須產生新的增量 migration**：
> `.venv/Scripts/python.exe -m flask db migrate -m "描述"`（此步驟需要資料庫連線）。

種子帳號（密碼取自 `.env` 的 `SEED_PASSWORD`）：

| 帳號 | 姓名 | 角色 |
| --- | --- | --- |
| `admin` | 系統管理員 | 管理員 |
| `warehouse` | 倉管阿哲 | 倉管 |
| `purchasing` | 採購大明 | 採購 |
| `sales` | 業務小美 | 銷售 |
| `accounting` | 會計小陳 | 會計 |

> 種子帳號皆標記為「首次登入須修改密碼」，登入後會被導向更改密碼頁面。

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

## 環境變數

| 變數 | 必填 | 說明 |
| --- | --- | --- |
| `DATABASE_URL` | 是 | `postgresql+psycopg://<user>:<password>@<host>:5432/AILearn` |
| `SECRET_KEY` | 是 | session cookie 簽章用隨機字串；未設定則應用拒絕啟動 |
| `SEED_PASSWORD` | 是（僅種子） | 種子帳號初始密碼；未設定則 `flask seed` 拒絕執行 |
| `CORS_ORIGINS` | 否 | 允許的前端來源，逗號分隔（預設 localhost:5173） |
| `LOGIN_MAX_ATTEMPTS` | 否 | 登入失敗鎖定門檻（預設 5） |
| `LOGIN_LOCK_MINUTES` | 否 | 鎖定分鐘數（預設 15） |
| `SESSION_HOURS` | 否 | session 有效小時數（預設 8） |
| `SESSION_COOKIE_SECURE` | 否 | 正式環境（https）請設為 1 |
| `FLASK_DEBUG` | 否 | 開發除錯模式；正式環境不得開啟 |

## API 一覽

| 方法 | 路徑 | 權限 | 說明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公開 | 登入（連續失敗會鎖定） |
| POST | `/api/auth/logout` | 已登入 | 登出 |
| GET | `/api/auth/me` | 已登入 | 目前使用者 |
| POST | `/api/auth/change-password` | 已登入 | 更改密碼 |
| GET | `/api/stock/query?q=` | 全部角色 | 庫存查詢（在手量／可用量／在途量） |
| GET | `/api/stock/items/<id>/batches` | 全部角色 | 批次明細 |
| GET | `/api/items` | 全部角色 | 商品主檔 |
| POST | `/api/items` | 管理員 | 建立商品 |
| GET | `/api/suppliers` | 採購／銷售／會計／管理員 | 供應商主檔 |
| GET | `/api/customers` | 採購（遮蔽）／銷售／會計／管理員 | 客戶主檔 |
| GET | `/api/warehouses`、`/api/locations` | 會計／管理員 | 倉庫與庫存位置 |
| GET | `/api/audit-logs` | 會計／管理員 | 操作紀錄（唯讀） |
| GET | `/api/users`、`POST /api/users`、`PATCH /api/users/<id>`、`POST /api/users/<id>/unlock` | 管理員 | 帳號與角色管理 |
| GET | `/api/purchase-orders` | 全部角色 | 採購單列表（含已入庫／待入庫數量） |
| POST | `/api/purchase-orders` | 採購／管理員 | 建立草稿採購單 |
| GET | `/api/grn` | 倉管／採購／會計／管理員 | 入庫單列表 |
| POST | `/api/grn` | 倉管／管理員 | **入庫（建立即過帳）**：對採購單入庫或手動入庫 |
| GET | `/api/grn/locations/<id>/items` | 倉管／管理員 | 位置入口入庫：該位置品項與數量 |
| POST | `/api/warehouses`、`POST /api/locations` | 管理員 | 建立倉庫／庫存位置 |
| GET | `/api/transfers/transfer-orders` | 倉管／採購／會計／管理員 | 調貨單列表 |
| POST | `/api/transfers/transfer-orders` | 倉管／管理員 | 建立調貨單（草稿） |
| POST | `/api/transfers/transfer-orders/<id>/ship` | 倉管／管理員 | 調貨出庫（數量轉為在途） |
| POST | `/api/transfers/transfer-orders/<id>/receive` | 倉管／管理員 | 調貨收貨（可少收，短缺留在在途） |
| POST | `/api/transfers/move` | 倉管／管理員 | 同倉移轉（總量守恆） |

## 測試

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q
```

> 測試以 **SQLite 記憶體資料庫**執行（`app/config.py` 的 `TestConfig`），**不需 PostgreSQL**，涵蓋切片 1 的驗收條件（AC-1 ~ AC-9）與 PRD §4.1 權限矩陣逐格驗證。
> 差異注意：SQLite 與 PostgreSQL 在 `Numeric`／`Decimal` 與 `ILIKE` 行為上略有差異，**真實 PostgreSQL 的驗證仍待補**（spec 任務 T-11）。

靜態檢查（選用）：

```powershell
.venv/Scripts/python.exe -m ruff check app tests
```

### 對真實 PostgreSQL 做端對端驗證

```powershell
backend\.venv\Scripts\python.exe backend\tools\verify_live.py
```

會啟動後端、以真實 HTTP 呼叫驗證登入／鎖定／權限矩陣／庫存數字／稽核紀錄／改密／登出，
再自動關閉後端。密碼取自 `backend/.env`，不會顯示。

## 常見問題

| 症狀 | 原因與處理 |
| --- | --- |
| 啟動即報「缺少 SECRET_KEY」 | `backend/.env` 未設定或未被讀取。`.env` 必須放在 `backend/` 目錄下。 |
| `fe_sendauth: no password supplied` | `DATABASE_URL` 未帶密碼，或密碼與角色不符。 |
| `flask db upgrade` 報「Directory 'migrations' does not exist」 | 需在 `backend/` 目錄下執行，且 `migrations/` 已隨程式碼提交。 |
| `flask seed` 報「未提供密碼」 | 設定 `SEED_PASSWORD` 或在提示時輸入。 |
| 登入後立刻被導回登入頁 | session cookie 失效（預設 8 小時），前端會自動導回 `/login`。 |
| 看不到某個主檔頁籤 | 依 PRD §4.1 權限矩陣，倉管不可見供應商／客戶／倉庫／位置。 |

## 資安原則（PRD §3、§4.9、addendum §3）

- 密碼以 bcrypt 單向雜湊儲存；**任何明文密碼不得進入版控、投影片、對話紀錄或日誌**。
- `.env` 已被 `.gitignore` 排除；連線字串以環境變數注入。
- 連線字串使用**最小權限的專用角色**（`ailearn_app`），不使用 `postgres` 超級使用者帳號。
- 角色權限一律在**伺服器端**檢查；前端隱藏按鈕不算通過。
- 操作紀錄（`audit_logs`）只增不改，無刪除 API。

## 介面與風格

- **左側固定導覽**（深色）+ 頂部頁面標題列，取代原本的橫向選單
- 配色：石板灰 + 靛藍（`--primary: #4f46e5`），狀態色分明（成功／危險／提醒）
- 卡片（`.card`）、面板（`.panel`）、表格（固定表頭、數字右對齊、hover、橫向捲動）
- 登入頁改為「左側品牌區 + 右側表單」雙欄
- 庫存查詢頁新增三張統計卡（商品數、在手量合計、在途量合計）
- 支援窄螢幕：側邊欄轉為橫向列

## 目前交付範圍

**已完成（切片 1、2、3）**
- 帳密登入／登出／改密、五角色權限矩陣（伺服器端）、連續失敗鎖定、稽核紀錄（不可刪除）
- 商品／供應商／客戶／倉庫／位置主檔、庫存查詢（在手量／可用量／在途量、模糊搜尋、展開明細）
- 帳號與角色管理（建立／停用／改角色／重設密碼／解除鎖定）
- **入庫**：採購單入庫、位置入庫、手動入庫（管理員）；入庫即建立批次、寫入庫存異動帳、庫存數字即時更新
- **移轉與調貨**：同倉移轉（總量守恆）、跨倉調貨兩段式（出庫 → 在途 → 收貨）、批次沿用、短缺記錄
- 種子資料、驗收測試（80 項）、真實 PostgreSQL 端對端驗證工具

**尚未開放（後續切片）**
- 領用出庫（需銷貨單先存在）、配置量、負庫存防護的其餘路徑（切片 4 之後）
- 銷貨單、FIFO 成本取用、毛利試算、反向單據（切片 4）
- 採購單狀態機、水位設定與警示清單、採購單結案（切片 5）
- 寄貨閉環、盤點、調整與報廢、報表與匯出、列印（切片 6）
