---
title: MVP 切片 1：登入、權限與庫存查詢
spec_id: mvp-slice-1
route: dispatch
status: done
created: 2026-10-21
updated: 2026-10-21
date: 2026-10-21
baseline_commit: 13a08e0
review_loop_iteration: 0
---

# MVP 切片 1：登入、權限與庫存查詢

## Intent

<frozen-after-approval>
使用者目標：**倉管人員登入後，看得到每個商品在哪個倉庫、哪個庫存位置、還剩多少（在手量／可用量），並能依商品名稱或編號快速定位。**

本次只交付這一個目標。基礎地層（資料模型、migration、權限機制、種子資料）一併建好，但**入庫、出貨、調貨、銷貨、採購、報表等功能本切片不開放**，屬後續切片。

對應 PRD：FR-1（登入／登出）、FR-2（角色權限）、FR-3（稽核紀錄）、FR-6（商品查詢）、FR-12（快速定位）、FR-26（帳號與角色管理）、FR-8（倉庫與位置）、FR-4（商品主檔）、FR-20（供應商）、FR-32（客戶主檔）。
</frozen-after-approval>

## Scope

**包含**
1. 後端骨架：Flask app factory、Flask-SQLAlchemy、Flask-Migrate、PostgreSQL `AILearn`、CORS、環境變數設定。
2. 完整資料模型（一次建好，避免後續切片反覆改 schema）：users / items / suppliers / item_suppliers / customers / warehouses / locations / batches / purchase_orders / grn / sales_orders / shipping_orders / transfer_orders / returns / stock_adjustments / stocktakes / stock_ledger / stock_balances / allocations / cost_consumptions / audit_log / reorder_points。
3. 認證：以 session cookie 登入／登出／查詢目前使用者；bcrypt 密碼雜湊；連續 5 次失敗鎖定 15 分鐘；角色裝飾器在**伺服器端**檢查。
4. 主檔 API（讀取為主，建立僅限對應角色）。
5. 庫存查詢 API：商品清單（在手量／可用量／在途量）、依名稱或編號模糊查詢、批次明細。
6. 前端 React（Vite）：登入頁、庫存查詢頁、主檔瀏覽頁、角色導覽。
7. 種子資料：5 種角色帳號、2 個實體倉 + TRANSIT 虛擬位置、位置、供應商、商品、批次、庫存異動帳與餘額、客戶。
8. 部署說明（README）：`.env`、migration、seed、啟動前後端。

**不包含（本切片）**
- 入庫、領用、移轉、調貨、盤點、調整單、銷貨、寄貨、採購、報表、列印、匯出。
- 條碼、權杖、多單位、批次效期警示、客戶主檔的完整 CRUD（僅讀取）。

## Acceptance Criteria

**AC-1 登入成功**
- Given 一個啟用中的 `warehouse` 帳號與正確密碼，When 呼叫 `POST /api/auth/login`，Then 回傳 200 與 `{username, name, role}`，且後續請求帶 session cookie 可存取受保護端點。
- Given 密碼錯誤，When 呼叫登入，Then 回傳 401 且訊息固定為「帳號或密碼錯誤」，不透露帳號是否存在。

**AC-2 連續失敗鎖定**
- Given 同一帳號連續 5 次密碼錯誤，When 第 5 次後再嘗試登入（即使密碼正確），Then 回傳 423 且帳號鎖定 15 分鐘；鎖定與解除事件寫入 `audit_log`。

**AC-3 未登入不可存取**
- Given 未登入狀態，When 呼叫任何 `/api/*` 業務端點，Then 回傳 401，且不洩漏資料。

**AC-4 伺服器端角色控管**
- Given 以 `sales` 角色登入，When 呼叫 `POST /api/items`（僅管理員），Then 回傳 403。
- Given 以 `warehouse` 角色登入，When 呼叫 `GET /api/stock/query`，Then 回傳 200 與各倉在手量／可用量。
- Given 權限檢查只在前端隱藏按鈕，When 直接呼叫 API，Then 仍被伺服器端拒絕。

**AC-5 庫存查詢數字一致**
- Given 種子資料中商品 IT-000001 在南港倉 A-01 有 120 件且無配置，When 查詢庫存，Then 該位置在手量 = 120、可用量 = 120、在途量 = 0。
- Given 查詢回應中任一商品，Then 在手量 = 該商品所有位置（含 TRANSIT）的 ledger 合計；可用量 = 在手量 − 該商品 `allocations` 合計。

**AC-6 快速定位**
- Given 輸入部分商品名稱「螺絲」，When 呼叫 `GET /api/stock/query?q=螺絲`，Then 回傳所有含「螺絲」的商品，結果上限 50 筆。
- Given 查詢結果，Then 依商品層級可用量合計由大到小排序。

**AC-7 稽核紀錄**
- Given 任何登入成功、登入失敗、鎖定、登出、主檔建立，When 發生，Then `audit_log` 有一筆對應紀錄，且不可透過 API 刪除或修改。

**AC-8 種子資料可重建**
- Given 一個全新的空資料庫，When 執行 `flask db upgrade` 與 `flask seed`，Then 得到可登入的 5 種角色帳號與可查詢的庫存資料，且可重複執行（冪等）。

**AC-9 前端流程**
- Given 使用者開啟前端，When 輸入錯誤帳密，Then 顯示「帳號或密碼錯誤」；輸入正確帳密，Then 進入庫存查詢頁並可搜尋商品、看到位置與數量。
- Given 未登入直接開啟受保護路由，Then 導向登入頁。

## Code Map

- `backend/app/__init__.py` — `create_app()` app factory，註冊 extensions、blueprints、CLI 指令。
- `backend/app/config.py` — 從環境變數讀 `DATABASE_URL`、`SECRET_KEY`、`CORS_ORIGINS`。
- `backend/app/extensions.py` — `db`、`migrate` 實例（避免循環 import）。
- `backend/app/models.py` — 全部資料模型；**改動此檔等同改 schema，必須同步產生 migration**。
- `backend/app/security.py` — bcrypt 雜湊／驗證、登入失敗鎖定判定。
- `backend/app/auth.py` — `/api/auth/*` 與 `require_roles` 裝飾器。
- `backend/app/api/masterdata.py` — 主檔讀取／建立 API。
- `backend/app/api/stock.py` — 庫存查詢 API（在手量／可用量／在途量）。
- `backend/app/seed.py` — 種子資料（`flask seed`）。
- `backend/wsgi.py` — `FLASK_APP` 進入點。
- `frontend/src/api.js` — fetch 包裝，自動帶 cookie。
- `frontend/src/pages/*` — 頁面元件。
- `backend/.env` — **不進版控**（`.gitignore`），僅存本機連線字串與 SECRET_KEY。
- `_bmad-output/planning-artifacts/prds/prd-庫存管理系統-2026-10-21/prd.md` — 需求來源，**本切片實作不得與其衝突**。

## Implementation Notes

- **可用量定義**（不可簡化）：在手量 = `stock_balances` 合計（含 TRANSIT 位置）；可用量 = 在手量 − `allocations` 合計。本切片 `allocations` 為空，故可用量 = 在手量，但**程式必須照此公式實作**，不可硬編碼。
- **在途位置**：`warehouses` 表以 `is_virtual` 標記 TRANSIT，位置代碼 `TRANSIT`；查詢時實體倉合計需扣除在途。
- **Migration 策略**：一次建立全部資料表（PRD addendum §1.4 的清單），之後切片只加欄位、不重寫。`flask db migrate -m "initial schema"` + `upgrade`。
- **不建立 `GRANT`／`REVOKE` 等權限機制**：角色權限在應用層以 `require_roles` 檢查，資料庫連線使用專用 app 角色（僅該庫權限）。
- **前端**：Vite + React 18 + react-router；`vite.config.js` 以 proxy 將 `/api` 轉到 `http://127.0.0.1:5000`，避免 CORS 與 cookie 問題（開發環境）。
- **不寫入任何明文密碼**：種子資料的預設密碼以環境變數 `SEED_PASSWORD` 帶入，預設值僅供本機示範，且必須在 README 標示「首次登入後請修改」。
- **不做**：條碼、權杖、多單位、PDF/列印、報表、匯出、離線、快取、RTL、國際化。

## Tasks & Acceptance

- [x] T-1 後端骨架：`create_app()`、設定、extensions、Flask-Migrate 綁定、錯誤處理
- [x] T-2 完整資料模型（29 張表，含 `allocations`、`cost_consumptions`、`stock_adjustments`、`returns`、`customers`、`reorder_points`、TRANSIT 虛擬位置）
- [x] T-3 認證：登入／登出／me、bcrypt、連續 5 次失敗鎖定 15 分鐘、鎖定與解鎖事件稽核
- [x] T-4 伺服器端角色權限：`require_roles` 裝飾器 + PRD §4.1 矩陣逐格驗證 + 採購看不到客戶身分
- [x] T-5 主檔 API：items（列表／建立）、suppliers、customers、warehouses、locations（依矩陣限制可見）
- [x] T-6 庫存查詢 API：模糊搜尋、在手量／可用量／在途量、展開位置明細、依可用量排序、total 為符合筆數
- [x] T-7 種子資料：5 種角色帳號、2 實體倉 + TRANSIT、位置、供應商、客戶、5 商品、9 批次、11 筆異動帳、冪等
- [x] T-8 前端 React：登入頁、庫存查詢頁、主檔瀏覽頁、角色導覽、未登入導向、401 自動導回、錯誤邊界
- [x] T-9 測試：43 項 pytest 驗收測試涵蓋 AC-1 ~ AC-9 與權限矩陣
- [x] T-10 文件：README（設定、migration、seed、API 一覽、環境變數、常見問題、資安原則）、`.env.example`、`.gitignore`、`.gitattributes`、`pyproject.toml`（pytest/ruff 設定）
- [x] T-12 初始 migration 產出：`backend/migrations/versions/0001_initial_schema.py`（由 `tools/generate_initial_migration.py` 產生，不需 DB 連線）
- [x] T-13 審查修補（見 Review Triage Log）：時間戳預設值、可用量以 ledger 為準、權限矩陣落地、輸入驗證、稽核讀取端點、改密流程、種子冪等
- [ ] T-11 在真實 PostgreSQL 上執行 `flask db upgrade` 與 `flask seed`（**待 PostgreSQL 密碼**；目前以 SQLite 記憶體庫驗證）

## Verification

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q     # 43 passed
cd ..\frontend; npm run build                     # built successfully
```

## Spec Change Log

- 2026-10-21 初版建立。實作期間未修改 `<frozen-after-approval>` 區塊。
- 實作發現：種子資料的批次編號原以商品索引產生，會重複（同一商品多個位置）。已於 `app/seed.py` 改為固定序號（可重跑辨識同一批資料）；在途示範改為「同一批次由中港倉移出 15 件至 TRANSIT」，使批次剩餘量守恆。
- 實作發現：`datetime.utcnow()` 於 Python 3.12+ 為棄用 API。已新增 `app/timeutil.py` 提供 `utcnow()` 並全面取代。
- 審查後：`default=utcnow()` / `default=dt.date.today` 的括號會讓預設值在 import 時求值一次（所有列共用同一時間戳），已改為傳遞 callable。

## Review Triage Log

| 發現 | 判定 | 證據 | 路由 |
| --- | --- | --- | --- |
| `default=utcnow()` 在 import 時求值，所有列共用同一時間戳（含 `audit_logs.created_at`） | high | 讀 `models.py` 確認 `default=utcnow()` 會立即呼叫；`default=dt.date.today` 同型 | patch（已修：改傳 callable） |
| 缺少 migration，`flask db upgrade` 無法建立 schema | high | 驗證落差審查實測 `flask db history` 無 revision | patch（已修：產出 0001_initial_schema.py，29 表） |
| 在手量取自 `stock_balances` 快取而非 ledger，兩表分歧時數字會落後 | high | 改以 `stock_ledger` 為唯一來源，並回傳 `balance_diff` | patch（已修 + 新增測試） |
| 「已分配」無存放位置，可用量被高估（無對應餘額的配置被忽略） | high | 審查指出配置與餘額的 join 會丟失孤兒配置 | patch（已修：商品層可用量 = 在手量 − 全部有效配置；位置層另計） |
| PRD §4.1 權限矩陣未套用於主檔讀取（倉管可讀供應商／客戶／倉庫／位置） | high | 逐格比對矩陣與 `READABLE_BY` | patch（已修 + 矩陣參數化測試） |
| 採購可見客戶聯絡人與電話，遮蔽不完整 | medium | PRD §4.1：採購不得見客戶名稱 | patch（已修：整列遮蔽） |
| 種子資料以「整張 ledger 是否為空」守衛，已有資料時完全不會產生庫存 | medium | 讀 `seed.py` 守衛邏輯 | patch（已修：改為逐批次判斷 + 固定批次序號） |
| 重跑種子會覆蓋既有帳號的角色 | medium | 讀 `seed.py` 使用者迴圈 | patch（已修：既有帳號不覆蓋角色／姓名） |
| 鎖定期過後失敗次數未歸零，一次錯誤即重新鎖定 | medium | 讀 `security.is_locked` 邏輯 | patch（已修：到期時歸零並寫 ACCOUNT_UNLOCKED） |
| 密碼長度超過 72 bytes 使 bcrypt 拋例外 | medium | bcrypt 5.0 限制 | patch（已修：明確拒絕並回 400） |
| `SECRET_KEY`／`SEED_PASSWORD` 有公開預設值，缺 `.env` 仍可啟動 | medium | 讀 `config.py` 預設值 | patch（已修：SECRET_KEY 缺失即拒絕啟動；seed 無密碼即拒絕執行） |
| `limit` 參數未驗證，`?limit=abc` 造成 500 | medium | 讀兩支 API | patch（已修：共用 `int_arg` 夾限） |
| `POST /api/items` 接受非數字／超範圍金額，拋 500 | medium | 讀 `_to_decimal` | patch（已修：型別與範圍驗證，錯誤回 400） |
| 缺少「更改密碼」流程，但種子帳號標記必須改密 | medium | 讀 `auth.py` 無此端點 | patch（已修：新增端點 + 前端頁面 + 首次登入導向） |
| 缺少稽核紀錄讀取端點，FR-3「任何時間點可查」無法滿足 | medium | 讀 `models.AuditLog` 只寫不讀 | patch（已修：新增 `/api/audit-logs` 唯讀端點 + 前端頁） |
| 500 錯誤未 rollback，SQLAlchemy session 狀態殘留 | medium | 讀 `__init__.py` | patch（已修：500 handler rollback + teardown 移除 session） |
| `wsgi.py` 直接執行時開啟 Werkzeug 除錯器 | medium | 讀 `wsgi.py` | patch（已修：改由 `FLASK_DEBUG`  控制） |
| `load_dotenv()` 未指定路徑，換工作目錄即讀不到設定 | medium | 讀 `config.py` | patch（已修：以檔案位置推導） |
| 前端：session 過期不導回登入、列展開不能用鍵盤、`target_margin_rate = 0` 被當缺值 | medium | 審查指出；讀前端原始碼確認 | patch（已修：401 事件導向、鍵盤操作與 aria、null 判斷） |
| 前端：主檔頁對所有角色顯示全部頁籤 | medium | PRD §4.1 矩陣 | patch（已修：依角色過濾頁籤與導覽） |
| 稽核事件（鎖定／登出／建立商品／越權）無測試釘住 | medium | 驗證落差審查指出測試只斷言 LOGIN_* | patch（已修：逐事件斷言） |
| 缺少 CSRF token 機制 | medium | 審查指出；PRD §4.9 未列 CSRF | defer（已記入 deferred-work.md） |
| 缺少前端測試、前端 lint、CI、正式 WSGI 伺服器、容器化 | low | 審查指出 | defer（已記入 deferred-work.md） |
| `stock_balances` 與 ledger 的一致性無強制對帳 | low | 寫入路徑於切片 2、3 尚未實作 | defer（已記入 deferred-work.md，於切片 2 以服務層落實） |
| 審查指出「mojibake 中文字串」 | false | 原始碼為 UTF-8，測試斷言「帳號或密碼錯誤」通過；問題出在審查者讀到的 diff 檔編碼 | 無動作 |

## Deferred Work

- 切片 2：入庫（FR-9、FR-27、FR-5）與庫存異動帳寫入
- 切片 3：領用出庫與跨倉調貨（FR-10、FR-11、FR-18、FR-31、配置量）
- 切片 4：銷貨單與毛利（FR-14 ~ FR-17、FR-19、FR-29）
- 切片 5：採購與水位警示（FR-20 ~ FR-23）
- 切片 6：寄貨、調整、盤點與報表（FR-13、FR-24、FR-25、FR-28、FR-30）
