---
title: MVP 切片 2：入庫、批次建立與庫存異動帳寫入
spec_id: mvp-slice-2
route: dispatch
status: done
created: 2026-10-21
updated: 2026-10-21
date: 2026-10-21
baseline_commit: c6d0e9d
review_loop_iteration: 0
---

# MVP 切片 2：入庫、批次建立與庫存異動帳寫入

## Intent

<frozen-after-approval>
使用者目標：**倉管人員收貨時，輸入商品、數量、實際單價與放置位置並送出，系統立刻建立批次、寫入庫存異動帳，庫存數字當場對得上；管理員也能在沒有採購單時手動入庫（需填原因）。**

這是系統第一個會改變資料的功能。因此本切片的核心不是「多一個表單」，而是**建立唯一的庫存寫入服務層**：所有庫存異動都經過同一個入口，才能保證「異動帳是唯一事實來源」「餘額與異動帳永不分歧」「任何異動都留下稽核紀錄」。

對應 PRD：FR-5（批次建立）、FR-8（倉庫與位置維護）、FR-9（入庫）、FR-23（採購單最小可用：建立與待入庫數量）、FR-27（以位置為入口的入庫）、FR-31（負庫存全域防護）、FR-3（稽核紀錄）、FR-25（庫存結構報表的基礎）。
</frozen-after-approval>

## Scope

**包含**
1. **庫存寫入服務層**（`app/services/stock_service.py`）：單一寫入入口，負責
   - 以資料庫交易過帳（失敗整筆回滾）
   - 對庫存餘額列取得列鎖（`SELECT ... FOR UPDATE`），防止併發超賣
   - 寫入 `stock_ledger`（唯一事實來源）並同步更新 `stock_balances`（快取）
   - 寫入 `audit_logs`（同一交易）
   - 負庫存防護：任何路徑後可用量不得為負
2. **入庫單 API**：
   - `GET /api/purchase-orders`：採購單列表（含待入庫數量）
   - `POST /api/purchase-orders`：建立草稿採購單（採購／管理員）
   - `POST /api/grn`：對採購單入庫或手動入庫，**建立即過帳**（一次交易完成）
   - `GET /api/grn`：入庫單列表
3. **批次建立**：入庫過帳時依 `B-YYYYMMDD-NNN` 建立批次（PRD FR-5）
4. **倉庫與位置建立**（管理員）：`POST /api/warehouses`、`POST /api/locations`
5. **前端入庫頁**：選採購單 → 帶出明細 → 填實際數量／實際單價／位置 → 送出；手動入庫；位置入口入庫
6. **測試**：服務層與 API 測試，驗證 ledger／balances／批次／稽核四者一致

**不包含（本切片）**
- 採購單的「已送出」狀態、水位設定與警示清單、採購單結案 → 切片 5
- 領用出庫、跨倉調貨、配置量 → 切片 3
- 盤點、調整單、報廢 → 切片 6
- 成本評價（毛利用）、FIFO 成本取用 → 切片 4
- 退回／反向單據 → 切片 4

## Key Decisions（本切片的規則定義）

這些是 PRD 已定義、但需要落到實作層的規則；實作必須遵守，不得另行發明。

| 規則 | 內容 |
| --- | --- |
| 入庫語意 | **建立即過帳**：不存在「草稿入庫單」。送出後立即建立批次、寫入 ledger、更新餘額，之後不可修改（更正走切片 4/6 的反向單據與調整單） |
| 批次編號 | `B-YYYYMMDD-NNN`，日期為**入庫當日**，序號為當日流水（不足三位補 0） |
| 批次數量 | 以**實際入庫數量**為準（不是採購單數量） |
| 成本 | 批次成本 = **實際入庫單價**（不是採購單預估單價） |
| 待入庫數量 | 採購單行的 `待入庫 = 訂購數量 − 已入庫數量`；入庫數量不得超過待入庫數量 |
| 手動入庫 | 僅管理員；必須填寫原因；同樣建立批次與寫入 ledger |
| 位置入口入庫 | 輸入位置代碼 → 顯示該位置品項 → 對指定品項入庫（FR-27） |
| 一致性 | `stock_balances` 是 `stock_ledger` 的快取；每次入庫後兩者必須相等（`balance_diff` 恆為 0） |
| 負庫存 | 入庫不會造成負庫存，但**所有**寫入路徑共用同一道防護；其他路徑（切片 3）沿用同一服務層 |

## Acceptance Criteria

**AC-1 對採購單入庫**
- Given 一張草稿採購單含一行「IT-000001 × 100」，When 倉管以實際數量 95、實際單價 46、位置「南港倉 A-01」入庫，Then 回傳入庫單編號 `GR-YYYYMMDD-NNN`，且該商品在 A-01 的在手量增加 95。
- Given 同一張採購單，When 再次入庫 10 件，Then 成功，且該行待入庫數量由 5 變為 0（總入庫 105 > 訂購 100 應被拒絕，見 AC-2）。

**AC-2 超過待入庫數量被拒**
- Given 採購單待入庫數量為 5，When 入庫 6 件，Then 回傳 400 且錯誤訊息指出剩餘待入庫數量，庫存不受影響。

**AC-3 批次建立**
- Given 完成一次入庫，When 查詢批次，Then 存在批次 `B-YYYYMMDD-NNN`，其商品、來源採購單、**實際入庫單價**、數量、入庫日期正確。

**AC-4 異動帳與餘額一致**
- Given 完成入庫，When 查詢庫存，Then `balance_diff` 為 0；在手量等於「入庫前 + 本次入庫量」。

**AC-5 稽核紀錄**
- Given 完成入庫，When 查詢操作紀錄，Then 有一筆 `GRN_POSTED` 紀錄，含操作人員、數量、位置、批次編號。

**AC-6 手動入庫**
- Given 倉管角色，When 手動入庫，Then 403。
- Given 管理員角色，When 手動入庫且未填原因，Then 400。
- Given 管理員角色，When 手動入庫且填寫原因，Then 成功並建立批次。

**AC-7 位置入口入庫**
- Given 輸入存在的位置代碼，When 查詢該位置品項，Then 回傳該位置的品項與數量；選取品項入庫後，該位置數量增加。
- Given 輸入不存在的位置代碼，Then 回傳 400 並列出可用位置。

**AC-8 負庫存防護**
- Given 任何入庫路徑，When 執行完，Then 該商品所有位置的可用量皆 ≥ 0（入庫本身不會造成負值，但此約束由服務層統一保證）。

**AC-9 權限**
- Given 採購角色，When 查詢採購單與入庫單，Then 200。
- Given 會計角色，When 查詢入庫單，Then 200（唯讀）。
- Given 銷售角色，When 建立入庫單，Then 403。

**AC-10 種子資料不變**
- Given 執行入庫功能後，When 重新執行 `flask seed`，Then 種子資料不會重複建立（入庫是既有資料的異動，不影響冪等性）。

## Code Map

- `backend/app/services/stock_service.py`（**新建**）— 唯一的庫存寫入入口：`post_grn()`。其他切片的所有庫存異動都必須走這裡。
- `backend/app/models.py` — 已有 `Grn`、`GrnLine`、`Batch`、`StockLedger`、`StockBalance`、`PurchaseOrder`、`PurchaseOrderLine`；本切片可能微調欄位（需新增 migration）。
- `backend/app/api/stock.py` — 既有查詢 API（只讀）；本切片不改其語意，但其數字必須與寫入後的 ledger 一致。
- `backend/app/api/masterdata.py` — 既有主檔 API；本切片新增倉庫／位置建立端點。
- `backend/app/api/purchase.py`（**新建**）— 採購單列表與建立。
- `backend/app/api/receiving.py`（**新建**）— 入庫單建立（過帳）與列表。
- `backend/app/security.py` — `write_audit()` 稽核寫入。
- `backend/app/extensions.py` — `db` 實例，交易與列鎖在此層操作。
- `frontend/src/pages/Receiving.jsx`（**新建**）— 入庫頁。
- `frontend/src/components/Layout.jsx` — 導覽（需加入入庫頁籤，依角色）。
- `frontend/src/api.js` — API 封裝（需加入新端點）。
- `backend/tools/generate_initial_migration.py` — **僅在表結構有變動時**用於產生新增 migration。
- `_bmad-output/planning-artifacts/prds/prd-庫存管理系統-2026-10-21/prd.md` — 需求來源，**不得與其衝突**。

## Implementation Notes

- **服務層是重點**：`post_grn()` 必須用 `with db.session.begin():` 或等效方式確保「批次 + ledger + balances + audit」四者在同一交易；任何一步失敗整筆回滾。
- **列鎖**：對受影響的 `(item_id, batch_id, location_id)` 餘額列執行 `SELECT ... FOR UPDATE`（PostgreSQL 支援；SQLite 測試環境會忽略）。
- **快取與事實分離**：寫入時同時寫 ledger 與 balances；查詢仍以 ledger 為準（切片 1 已如此），`balance_diff` 用於自我檢查。
- **批次序號**：以當日已存在批次的最大序號 + 1 產生；同日重複入庫不會撞號（唯一鍵擋下時重試）。
- **不要在服務層之外寫 ledger**：任何繞過服務層直接寫 `stock_ledger` 的程式碼都是缺陷（審查會抓到）。
- **不實作**：草稿入庫單、庫存成本評價、負庫存沖銷、跨倉轉庫、待入庫結案、採購單狀態機。

## Tasks & Acceptance

- [x] T-1 庫存寫入服務層 `app/services/stock_service.py`：單一寫入入口、同一交易、列鎖、負庫存防護、稽核
- [x] T-2 單據編號產生器拆分（批次 `B…`、入庫單 `GR-…`、採購單 `PO-…` 各用自己的資料表來源）
- [x] T-3 採購單 API：建立草稿、列表（含已入庫／待入庫數量）
- [x] T-4 入庫 API：`POST /api/grn`（建立即過帳）、`GET /api/grn`、位置入口 `GET /api/grn/locations/<id>/items`
- [x] T-5 批次建立（入庫時建立，`B-YYYYMMDD-NNN`，成本＝實際入庫單價）
- [x] T-6 倉庫與位置建立端點（僅管理員）
- [x] T-7 前端入庫頁：採購單入庫、位置入庫、手動入庫（管理員）
- [x] T-8 測試：18 項切片 2 測試（AC-1 ~ AC-10）
- [x] T-9 migration：`grn_lines` 增加採購單明細關聯與備註（升降級循環已實測）
- [x] T-10 真實 PostgreSQL 端對端驗證：入庫流程 12 項檢查全數通過

## Verification

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q                       # 67 passed（SQLite）
cd ..\frontend; npm run build                                      # built successfully
backend\.venv\Scripts\python.exe backend\tools\verify_live.py      # 全部通過（含入庫流程，真實 PostgreSQL）
```

## Spec Change Log

- 2026-10-21 初版建立。`<frozen-after-approval>` 未修改。
- **PRD 修訂（v3.1）**：實作時發現 §4.1 權限矩陣把「倉庫／庫存位置」只列「維護」一列，導致倉管在入庫時無法選擇庫存位置（FR-9／FR-27 都需要）。已拆為「檢視」（全部角色可讀）與「維護」（僅管理員）兩列，並在 PRD 標明修訂理由；後端 `READABLE_BY` 與權限矩陣測試同步更新。
- 實作發現：初版 `next_daily_code` 同時供批次／入庫單／採購單使用，卻只查批次表，導致入庫單代號重複（unique 衝突）。已拆為 `next_batch_code`／`next_grn_code`／`next_po_code`，各查自己的表。
- 實作發現：位置入口清單初版查「入庫單明細」，會漏掉種子資料建立的存量。已改查**庫存異動帳**（該位置真正的存量）。

## Deferred Work

- 切片 3：領用出庫、跨倉調貨、配置量、負庫存防護的其餘路徑
- 切片 4：銷貨單、FIFO 成本取用、毛利試算、反向單據
- 切片 5：採購單狀態機、水位設定與警示清單、採購單結案
- 切片 6：盤點、調整單、報廢、報表與匯出
