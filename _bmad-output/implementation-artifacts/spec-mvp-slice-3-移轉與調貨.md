---
title: MVP 切片 3：庫存移轉與跨倉調貨
spec_id: mvp-slice-3
route: dispatch
status: done
created: 2026-10-21
updated: 2026-10-21
date: 2026-10-21
baseline_commit: 75b7512
review_loop_iteration: 0
---

# MVP 切片 3：庫存移轉與跨倉調貨

## Intent

<frozen-after-approval>
使用者目標：**倉管可以把庫存从一个庫存位置移到同倉的另一個位置，或把商品由一個倉庫調到另一個倉庫——調出時數量離開來源倉並顯示為「在途」，抵達後收貨進目的地倉，全程數字對得上、批次身分不變。**

本切片只做「移轉」與「調貨」兩種搬運動作。**領用出庫不包含在內**：PRD FR-10 規定領用必須關聯既有單據（銷貨單／寄貨單／調整單），而這兩種單據屬切片 4 與 6，尚不存在；先做會做出沒有來源的領用。因此領用改在切片 4（銷貨單）之後接續。

對應 PRD：FR-11（庫存移轉）、FR-18（調貨單）、FR-3（稽核紀錄）、FR-31（負庫存全域防護）、§3（在途位置 TRANSIT 的定義）。
</frozen-after-approval>

## Scope

**包含**
1. **服務層擴充**（`app/services/stock_service.py`）
   - `create_transfer()`：建立調貨單（草稿），檢查來源庫位可用量
   - `ship_transfer()`：出庫 → 來源位置減、在途位置加（同一交易、列鎖）
   - `receive_transfer()`：收貨 → 在途位置減、目的庫位加；可少收（短缺）
2. **同倉移轉**：`POST /api/transfers/move`（即時完成，來源位置 → 目標位置，總量守恆）
3. **跨倉調貨 API**：`GET/POST /api/transfer-orders`、`POST /api/transfer-orders/<id>/ship`、`POST /api/transfer-orders/<id>/receive`
4. **前端調貨頁**：建立調貨單 → 出庫 → 收貨
5. **測試**：移轉與調貨的餘額、在途、批次身分、短缺處理、權限

**不包含（本切片）**
- 領用出庫（切片 4 之後）
- 調貨短缺的調整單認列（切片 6；本切片短缺數量留在在途位置並記錄於調貨單行）
- 調貨的權限細分（收貨倉可否拒收：v1 由管理員與倉管皆可收貨）
- 調撥運費歸屬（PRD §5 排除）

## Key Decisions

| 規則 | 內容 |
| --- | --- |
| 移轉不改變總量 | 同倉移轉：來源位置 −N、目標位置 +N，批次剩餘量不變，**不產生在途** |
| 跨倉調貨兩段式 | 出庫（來源倉 → TRANSIT 虛擬位置）→ 收貨（TRANSIT → 目的倉庫位） |
| 批次身分沿用 | 調貨**不建立新批次**，商品與批次一路帶過去（PRD FR-11、FR-18） |
| 在途不計入可用量 | 在途位於虛擬位置，實體倉合計 = 在手量 − 在途量；可用量 = 實體倉合計 − 配置量（PRD §3） |
| 狀態機 | 草稿 → 在途 → 已收貨（可標記短缺） |
| 短缺處理 | 收貨數量少於調出數量時，短缺數量**留在在途位置**（守恆不破），並記錄於調貨單行的 `received_quantity`；實際認列（調整單）留待切片 6 |
| 調出上限 | 調出數量不得大於來源庫位的**可用量**（含在途的實體倉可用量） |
| 權限 | 建立／出庫／收貨：倉管與管理員；查詢：倉管、採購、會計、管理員 |

## Acceptance Criteria

**AC-1 同倉移轉**
- Given 某商品在南港 A-01 有 120 件，When 移轉 30 件到 A-02，Then A-01 為 90、A-02 為 30、**總量不變**、不產生在途。

**AC-2 跨倉調貨出庫**
- Given 某商品在中港 B-01 有 185 件，When 調出 50 件到南港，Then 中港減少 50、**在途量增加 50**、可用量同步下降、批次編號不變。

**AC-3 收貨**
- Given 調貨單狀態為在途，When 目的地倉收貨 50 件到 A-02，Then 在途量減少 50、南港 A-02 增加 50、調貨單狀態為已收貨。

**AC-4 短缺**
- Given 調出 50 件，When 只收到 45 件，Then 收貨數量記為 45、短缺 5 留在在途位置（總量守恆）、調貨單標記短缺。

**AC-5 超量調出被拒**
- Given 來源庫位可用量為 10，When 調出 11 件，Then 回傳 400 且庫存不受影響。

**AC-6 狀態機保護**
- Given 調貨單仍是草稿，When 直接收貨，Then 回傳 400（必須先出庫）。
- Given 調貨單已收貨，When 重複收貨，Then 回傳 400。

**AC-7 稽核**
- Given 完成出庫與收貨，When 查稽核紀錄，Then 分別有 `TRANSFER_SHIPPED` 與 `TRANSFER_RECEIVED` 紀錄，含數量、位置、批次。

**AC-8 權限**
- Given 銷售角色，When 建立調貨單，Then 403。

**AC-9 一致性**
- Given 完成任一搬運動作，When 查庫存，Then `balance_diff` 仍為 0，且 `在手量 = 實體倉合計 + 在途量`。

## Code Map

- `backend/app/services/stock_service.py` — **擴充**：移轉與調貨的寫入邏輯（唯一寫入入口）
- `backend/app/models.py` — `TransferOrderLine` 需新增 `received_quantity`（需 migration）
- `backend/app/api/transfers.py`（**新建**）— 移轉與調貨 API
- `backend/app/api/stock.py` — 查詢 API（只讀，語意已在切片 2 修正：在途不計入可用量）
- `frontend/src/pages/Transfers.jsx`（**新建**）— 調貨頁
- `frontend/src/components/Layout.jsx` — 導覽新增「調貨」頁籤（倉管／管理員）
- `backend/tools/verify_live.py` — 加入移轉／調貨的真實環境驗證

## Implementation Notes

- 所有搬運動作都必須經過服務層，不得直接寫 `stock_ledger`。
- 出庫與收貨各自是一個交易；跨倉調貨的兩段之間數量停在 TRANSIT 位置。
- TRANSIT 位置以 `warehouses.is_virtual = true` 找尋，不寫死 id。
- 移轉（同一位置 → 同一位置）應拒絕。

## Tasks & Acceptance

- [x] T-1 服務層擴充：`move_stock()`（同倉移轉）、`create_transfer()`、`ship_transfer()`、`receive_transfer()`（跨倉兩段式）
- [x] T-2 移轉 API：`POST /api/transfers/move`
- [x] T-3 調貨 API：`GET/POST /api/transfers/transfer-orders`、`POST .../<id>/ship`、`POST .../<id>/receive`
- [x] T-4 批次沿用原批次、不另建批次；在途位置以 `is_virtual` 動態取得
- [x] T-5 短缺處理：實收記錄於明細，短缺留在在途位置（守恆不破）
- [x] T-6 前端調貨頁：建立調貨單 → 出庫 → 收貨（批次可選、可顯示可用量）
- [x] T-7 測試：13 項切片 3 測試（AC-1 ~ AC-9）
- [x] T-8 migration：`transfer_order_lines.received_quantity`
- [x] T-9 真實 PostgreSQL 端對端驗證：調貨流程 16 項檢查全數通過

## Verification

```powershell
cd backend
.venv/Scripts/python.exe -m pytest tests -q                       # 80 passed（SQLite）
cd ..\frontend; npm run build                                      # built successfully
backend\.venv\Scripts\python.exe backend\tools\verify_live.py      # 全部通過（含入庫與調貨）
```

## Spec Change Log

- 2026-10-21 初版建立。`<frozen-after-approval>` 未修改。
- **切片順序調整（重要）**：本切片原規劃含「領用出庫」，實作時發現 PRD FR-10 規定領用必須關聯既有單據（銷貨單／寄貨單／調整單），而這些屬切片 4 與 6，尚未存在；先做會產生「沒有來源的領用」。因此**領用出庫改到切片 4 之後**，本切片只做移轉與調貨（不依賴其他單據）。
- **修正 PRD §3 語意（v3.2）**：實作時發現既有查詢 API 的「可用量」把**在途量算進去了**，違反 PRD §3「在途量不計入任一倉的可用量與在手量」。已修正為：可用量 =（在手量 − 在途量）− 配置量；並同步更新切片 1 的測試與真實環境驗證的恆等式。
- 實作發現：API 端點函式與服務層函式同名（`move_stock`）造成呼叫到錯誤的對象，已改為別名匯入。

## Deferred Work

- 領用出庫（需銷貨單／寄貨單先存在）→ 切片 4 之後
- 調貨短缺的調整單認列 → 切片 6
- 收貨倉的拒收／部分拒收權限細分 → v2
