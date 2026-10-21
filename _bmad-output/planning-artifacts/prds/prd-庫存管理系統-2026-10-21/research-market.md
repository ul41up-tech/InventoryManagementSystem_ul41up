# 庫存管理系統 PRD 市場與競品研究摘要

研究日期：2026-10-21 ｜ 用途：PRD 撰寫前之市場、競品與領域模式參考

---

## 1. 市場現況

1. 中小企業的庫存管理軟體大致分四類：(a) 商用大型 ERP 的庫存/WMS 模組（SAP S/4HANA、Oracle NetSuite、Microsoft Dynamics 365 SCM、Infor CloudSuite/WMS）；(b) 雲端 SaaS 進銷存（Zoho Inventory 免費到 US$249/組織/月，含多倉、批次序號、條碼、reorder point、使用者角色）；(c) 開源方案（Odoo Community 免費但關鍵進階功能在 Enterprise，約 US$25–36/人/月；ERPNext 完全開源、無人數限制）；(d) DIY 小工具（Excel 模板、Google Sheets 自製、Shopify App）。參考：[Zoho Inventory 官網與定價](https://www.zoho.com/inventory/)、[Odoo vs ERPNext 比較](https://docs.frappe.io/enterprise/competitive-comparisons/erpnext-vs-odoo)、[ERPNext vs Odoo TCO](https://beancount.io/blog/2026/07/20/erpnext-vs-odoo-bootstrapped-open-source-licensing-tco-guide)。
2. 現實普遍做法是「先手工後系統」：多數小公司用 Excel/Google Sheets 記帳，直到資料量或通路數撐不住才導入系統；導入門檻主要不是功能而是導入成本與教育訓練。參考：[Excel 模板做進銷存的優缺點](https://a1.digiwin.com/essay/essay-content.php?detail=1206)、[2026 進銷存系統選型 Top 10](https://nabi.104.com.tw/posts/nabi_post_2299ceac-a6eb-443b-a943-428b6b693408)。
3. 台灣市場以「鼎新（Workflow ERP / 正航）、易飛、國內雲端進銷存」為代表，強項是繁中 UI、批次/效期與多倉庫，弱點常見為客製化成本高、介面偏舊、決策報表與毛利分析不足。參考：[正航 ERP 庫存管理](https://www.softwareic.com.tw/inventory.html)、[正航批號管理](http://www.join2.com.tw/info.asp?id=307)、[流通業多通路庫存與批號效期](https://www.digiwin.com.tw/blog/erp/3246.html)。
4. 雲端 SaaS 與電商通路整合已是基本期待（多通路同步、避免超賣），且小團隊的採購偏好「按組織/按月」而非大型 ERP 導入專案。參考：[Zoho Inventory 多通路](https://www.zoho.com/inventory/)、[多通路庫存管理 2026](https://www.prediko.io/blog/omnichannel-inventory-management)。
5. 市場上對「庫存帳實不符、缺貨與積壓並存、成本算不準」的不滿最普遍，中小廠商選型關鍵指標被歸納為：入庫掃碼、批次追蹤、安全庫存預警、呆滯分析四件事做扎實。參考：[中小企業庫存管理 ERP 選型實戰](https://blog.csdn.net/weixin_29041195/article/details/165649455)。

---

## 2. 競品 / 標竿（6 個）

### 2.1 Oracle NetSuite（雲端 ERP，含 WMS）
- 定位：中大型企業雲端 ERP，庫存為核心模組。
- 值得借鑑：多倉/多通路即時庫存視圖；FEFO（First Expiry First Out）批次揀貨與效期管理、批次號指派套件；lot/serial 完整可追溯；Prevent Negative Inventory 偏好設定；ABC 分析；多倉 transfer 與在途庫存。參考：[NetSuite Inventory](https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/inventory-management.shtml)、[FEFO Lot Assignments](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_161009052865.html)、[Prevent Negative Inventory](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1521526008.html)、[ABC Inventory Analysis](https://www.netsuite.com/portal/resource/articles/inventory-management/abc-inventory-analysis.shtml)。
- 明顯不做／弱：總成本高、客製與區域稅務複雜度大、對純小型單倉案的 UI 過重；毛利/折扣分析非其強項。

### 2.2 Microsoft Dynamics 365 Supply Chain Management
- 定位：中大型企業端到端供應鏈（WMS + 規劃）。
- 值得借鑑：warehouse/work pool 概念、供應鏈規劃（需求預測、庫存最佳化）、進銷貨流程與品質控管分工。參考：[Dynamics 365 SCM](https://www.microsoft.com/en-us/dynamics-365/products/supply-chain-management)、[Warehouse management overview](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-management-overview)。
- 明顯不做／弱：偏大型企業流程、實作顧問成本高、需大量設定學習曲線，不適合小團隊快速上手。

### 2.3 Odoo（Community + Enterprise，開源核心）
- 定位：模組化開源 ERP，Inventory 模組覆蓋 WMS 核心。
- 值得借鑑：庫存「雙重記帳（double-entry stock ledger）」觀念；多倉庫 + 調撥路徑（以 Transit Location 作中介，產生 outgoing delivery + incoming receipt）；Reordering Rules（min/max qty、multiple qty、UoM、每日排程 scheduler）；批次/序號（Lots/Serial Numbers）完整追溯；條碼作業；Cycle counting；landed costs（進貨成本分攤）。參考：[Odoo 庫存功能](https://www.odoo.com/app/inventory-features)、[倉庫間調撥文件](https://www.odoo.com/documentation/16.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/warehouse_replenishment_transfer.html)、[Lots/Serial Numbers](https://www.odoo.com/documentation/15.0/applications/inventory_and_mrp/inventory/management/lots_serial_numbers/lots.html)。
- 明顯不做／弱：預設允許負庫存且無警示（社群常見痛點，需靠 Studio/OCA 模組補）；Community 版缺少多數進階 WMS 與官方支援；術語與設定深度對非技術人員不友善。參考：[Odoo 負庫存預設值與防制](https://www.braincuber.com/blog/odoo-negative-stock-prevention-configuration)、[OCA Stock Disallow Negative](https://apps.odoo-community.org/modules/stock_no_negative)、[Community 與 Enterprise 差異](https://www.devolute.org/en/insights/open-source/odoo-vs-openproject-vs-erpnext)。

### 2.4 ERPNext / Frappe（完全開源，Stock 模組）
- 定位：開源全功能 ERP，Stock 模組支援多倉、序號/批次、成本評價。
- 值得借鑑：成本評價方法可選 FIFO 或 Moving Average，且文件用同一組數據示範兩者差異（FIFO 逐批耗用、移動平均每次進貨重算平均成本，會使毛利與期末存貨價值不同）；庫存成本可逐筆追蹤（valuation rate 依據運費、人工、原料等費用）；變更評價方法（有既存庫存時不可從移動平均改回 FIFO）。參考：[FIFO 與 Moving Average 差異](https://docs.frappe.io/erpnext/calculation-of-valuation-rate-in-fifo-and-moving-average)、[變更評價方法](https://docs.frappe.io/erpnext/change-valuation-method)、[批次別評價率已知問題](https://github.com/frappe/erpnext/issues/39226)。
- 明顯不做／弱：批次別評價率實作仍有 bug；介面與文件生態較弱；台灣在地稅務/發票/繁中在地化需自行處理。

### 2.5 Zoho Inventory（雲端 SaaS 進銷存，代表中小型市場）
- 定位：低門檻雲端進銷存，免費版 1 使用者 2 倉，Standard US$29/月、Premium US$129/月（依使用者與倉位数分級）。
- 值得借鑑：功能清單本身就是很好的 v1 需求 checklist——條碼/RFID、批次與序號追蹤、UoM 換算、低庫存 reorder point 提醒、庫存調整、地區稅別、報表、使用者角色與權限、客戶/供應商 portal、多通路同步、多倉 transfer order、backorder/dropship。參考：[Zoho Inventory 官網](https://www.zoho.com/inventory/)、[多倉管理](https://www.zoho.com/inventory/multi-warehouse-stock/)、[序號與批次](https://www.zoho.com/inventory/serial-batch-tracking/)。
- 明顯不做／弱：使用人數與倉位數依方案硬性限制；成本評價（批次成本）與毛利分析深度不如 ERP 級產品；審計軌跡細度不足。

### 2.6 Infor WMS / CloudSuite（中大型倉儲專業級）
- 定位：專業倉儲管理（WMS），含 3D 視覺、語音作業、AI 排程。
- 值得借鑑：「Auto Hold for Expired Inventory」——到期或接近效期的批次自動凍結，不可出庫；批次/庫位多層指派（lot × location）的倉儲詞彙模型。參考：[Infor WMS 文件 Auto Hold](https://docs.infor.com/wms/2026.x/en-us/wmsolh/chr1742459283230.html)、[Infor 倉儲詞彙表](https://docs.infor.com/ln/10.3/en-us/lnolh/help/wh/glossary/glossary.html)。
- 明顯不做／弱：屬企業級方案，成本與導入門檻遠超中小公司；偏倉內作業，銷售/採購/毛利面薄弱。

---

## 3. 通用需求模式（common domain patterns）

### 3.1 商品與識別
- SKU / 品號、條碼（Barcode/RFID）、商品群組（Item Group）、複合品/組件（Assembly/BOM）。參考：[Zoho 商品群組與複合品](https://www.zoho.com/inventory/item-groups-and-composite-items/)。
- 多單位（UoM）與換算率：同一商品以箱/瓶/個計價與出入庫。參考：[Zoho Inventory 特色](https://www.zoho.com/inventory/)。
- 供應商料號、客戶料號（跨平台比對）。

### 3.2 批次、序號與效期
- Lot/Batch 批次號、Serial 序號號、製效期（manufacture/expiry date）、庫齡（ageing）。
- 出貨揀貨策略：FEFO（先到期先出）、FIFO（先進先出）；過期批次凍結（Auto Hold）。參考：[NetSuite FEFO](https://www.crowe.com/ae/news/managing-perishable-inventory-with-fefo-in-netsuite-erp)、[Infor Auto Hold](https://docs.infor.com/wms/2026.x/en-us/wmsolh/chr1742459283230.html)。
- 追溯查詢：由成品回溯到批次、由批次回溯到進出貨單（traceability）。參考：[Odoo Lots/Serial](https://www.odoo.com/documentation/15.0/applications/inventory_and_mrp/inventory/management/lots_serial_numbers/lots.html)。

### 3.3 庫存數量語意（最常被搞混）
- 帳面量／在手量（On Hand）＝ 實體存在數量，包含已分配者。
- 可用量（Available）＝ On Hand − 已保留/已分配數量。
- 在途量（In Transit）、待驗量（Quality Hold）、已分配（Allocated/Reserved）。
- 「容易漏掉但實務上很重要」：只看一個「庫存量」數字會導致超賣；必須同時呈現 on hand 與 available。參考：[On Hand vs Available 差異](https://xorosoft.com/on-hand-vs-available-inventory/)、[Acctivate 說明](https://hub.acctivate.com/articles/difference-between-available-and-on-hand-quantities)、[SAP Community 討論](https://community.sap.com/t5/supply-chain-management-q-a/difference-between-on-hand-and-available-stock/qaq-p/13903926)。

### 3.4 補貨與水位
- 術語：安全庫存（Safety Stock）、再訂購點（Reorder Point）、最小/最大庫存（Min/Max）、經濟訂購量（EOQ）、前置時間（Lead Time）、需求變異。
- 公式：ROP =（平均每日用量 × 前置天數）+ 安全庫存。參考：[ROP 與安全庫存公式](https://gainsystems.com/blog/reorder-point-vs-safety-stock-balancing-inventory-in-retail/)、[SPS 公式](https://www.spscommerce.com/community/articles/how-to-calculate-safety-stock-formulas-and-methods-that-fit-your-data)。
- 「容易漏掉但實務上很重要」：水位應以「可用量」而非「在手量」觸發；同一 SKU 在不同倉的水位不同；要有供應商前置時間與下單量（multiple/EOQ）參數，否則補貨提醒會失真。

### 3.5 單據流程
- 採購：PO → 收貨（GRN，含批次、效期、實際數量、差異）→ 應付/GI；退回與退貨（Vendor Return）。
- 銷售：SO → 揀貨/出貨 → 開立發票 → 收款；銷售退回（RMA/Return Receipt）與退貨折讓。
- 調撥：Inter-warehouse Transfer Order，用 Transit Location / 在途倉記錄出庫與入庫之間的空窗。參考：[Odoo 倉間調撥](https://www.odoo.com/documentation/16.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/warehouse_replenishment_transfer.html)、[Sage Intacct Warehouse transfer](https://www.intacct.com/ia/docs/en_US/help_action/Inventory_Control/Using_Inventory_Control/Warehouse_transfers/warehouse-transfer-overview.htm)、[Odoo Transit Location 說明](https://octurasolutions.com/resources/inter-warehouse-transfers-in-odoo-19-replenishment-rules-and-transit-locations)。
- 盤點：全盤（Physical Inventory）與循環盤點（Cycle Counting），依 ABC 分級排程；盤點差異需經審核調整。參考：[Cycle counting 定義](https://www.methodusa.com/resources/what-is-cycle-counting)、[SAP Cycle Counting 課程](https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/applying-cycle-counting-optional)。
- 其他必備單據：借貨/寄售（借出/借入、Consignment）、報廢/損壞（Scrap）、盤盈盤虧調整。

### 3.6 成本、稅與毛利
- 成本評價法：FIFO、移動平均（Moving Average / Weighted Average）、標準成本、批次別評價（Landed Cost 進貨成本分攤：運費、關稅、稅費）。參考：[ERPNext FIFO vs 移動平均](https://docs.frappe.io/erpnext/calculation-of-valuation-rate-in-fifo-and-moving-average)、[正航進貨成本分攤](https://www.chi.com.tw/blog/purchasecaa)、[FIFO vs 加權平均](https://www.finaleinventory.com/guides/accounting-and-inventory-software/inventory-valuation-methods/)。
- 毛利 = 淨銷售額（扣折扣）− 銷貨成本；毛利額/毛利率；稅別（內稅/外稅、稅率）、單價含稅/未稅、折扣（品項折扣/整單折扣/階層價目表 Price List）。
- 「容易漏掉但實務上很重要」：毛利必須含運費、稅費、包材等費用攤提，否則熱銷商品可能賣越多虧越多（實務案例：折扣促銷帶來毛利率提升 ~15%）。參考：[毛利分析怎麼做](https://a1.digiwin.com/essay/essay-content.php?detail=1582)、[成本與毛利計算](https://www.jiandaoyun.com/blog/article/1060608/)、[費用漏算影響毛利](https://zhuanlan.zhihu.com/p/1975228114356441166)。

### 3.7 權限、審計與其他
- 角色權限（倉管/採購/銷售/會計）與職責分離（Segregation of Duties）；使用者層級的功能與資料範圍權限。
- 審計軌跡：誰、何時、對哪張單、做了什麼變更（含盤點差異、單價修改、成本調整）。參考：[ERP 角色式安全](https://xorosoft.com/role-based-security-keeping-your-data-safe-with-erp-systems/)、[ERP 控制與稽核](https://www.dawgen.global/erp-controls-audit-readiness-how-to-build-a-clean-trail-for-financial-statements-compliance-and-decision-making/)、[庫存稽核軌跡資料點](https://naologic.com/en/features/inventory-management/inventory-reporting)。
- 報表：庫存結存（數量與金額）、可用量、庫齡、呆滯/滯銷分析、ABC 分類、銷售毛利分析、盤點差異報表、調撥在途報表。
- 「容易漏掉但實務上很重要」：單據「草稿/待審/已核准/已過帳」狀態機與核准控管（正航有「批次覆核」批次核准機制）、以及已過帳不可直接修改（只能反向單據沖銷），這是審計的基本要求。參考：[正航批次覆核](https://www.chi.com.tw/blog/batchauditma)。

---

## 4. 風險與常見失敗模式

1. **庫存帳實不符（Shrinkage / 盤點差異）**：主因為人員輸入錯誤、盤點時點錯、供應商出貨數量不符、損壞與盜損；後果是成本與毛利全部失真。應對：條碼/RFID、循環盤點 + ABC 分級、自動對帳、即時盤點差異報表。參考：[10 種庫存差異原因](https://www.netsuite.com/portal/resource/articles/inventory-management/inventory-discrepancies.shtml)、[庫存損耗 10 原因](https://www.stockount.com/articles/inventory-shrinkage-10-causes-fast-fixes-that-work)、[盤點與自動對帳](https://o2vend.com/blog/posts/what-is-the-inventory-discrepancy-preventing-lost-inventory-)。
2. **負庫存與超賣**：許多系統（含 Odoo）預設允許負庫存、無警告，負數會污染所有下游報表與毛利；多通路電商環境更易超賣（同步 app 常以輪詢間隔更新）。應對：負庫存阻擋 + 明確核准流程、可用量（扣除已分配）為下單依據、保守的 buffer。參考：[Odoo 負庫存預設](https://www.braincuber.com/blog/odoo-negative-stock-prevention-configuration)、[Odoo 論壇負庫存討論](https://www.odoo.com/forum/help-1/negative-balances-in-inventory-why-are-they-allowed-how-can-i-prevent-them-293539)、[多通路超賣](https://www.finaleinventory.com/blog/tips/ecommerce-tips-to-manage-multichannel-listings/)、[同步輪詢造成超賣](https://community.shopify.com/t/which-inventory-management-app-is-actually-worth-it-in-2026-whats-working-for-your-store/637559/9)。
3. **成本與毛利計算錯誤**：評價法（FIFO / 移動平均 / 批次別評價）混用或事後更改，會讓歷史成本與毛利不可比；批次別評價實作仍有已知 bug；費用（運費、關稅、稅費、折扣讓利）漏算導致毛利虛高。參考：[ERPNext 變更評價方法限制](https://docs.frappe.io/erpnext/change-valuation-method)、[批次別評價率 issue](https://github.com/frappe/erpnext/issues/39226)、[費用漏算與毛利](https://zhuanlan.zhihu.com/p/1975228114356441166)。
4. **權限過寬與缺乏審計軌跡**：所有人都能改庫存與成本、盤點差異可直接覆寫，導致內控失效且無法追責；ERP 控制實務上要求角色權限、職責分離與完整變更紀錄。參考：[職責分離與角色權限](https://blog.consensusintl.com/top-erp-controls-for-compliance)、[ERP 控制與稽核軌跡](https://www.datacor.com/resources/integrated-erp-definition-benefits)、[RBAC 與稽核](https://xorosoft.com/role-based-security-keeping-your-data-safe-with-erp-systems/)。
5. **多倉庫資料不一致／調撥遺失**：調撥出庫與入庫之間缺乏「在途」概念，導致庫存總量在途時短少或重複；各倉水位各自設定也會造成局部缺貨與他倉積壓。應對：Transit Location/在途倉、調撥單狀態機、調撥差異處理、跨倉補貨路徑。參考：[Odoo Transit Location](https://octurasolutions.com/resources/inter-warehouse-transfers-in-odoo-19-replenishment-rules-and-transit-locations)、[在途 vs 在轉](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/stock-in-transfer-vs-stock-in-transit-where-to-find-it-how-to-remove-it/ba-p/13577561)。

---

## 5. 對 v1 MVP 的啟示

1. **先做「一條完整且正確的庫存主線」**：商品（含 UoM、條碼）→ 庫存異動單據流（採購收貨、銷售出貨、調撥、盤點調整）→ 庫存餘額（on hand / available / in transit）→ 成本評價 → 毛利。這條線的正確性比功能數量重要，因為負庫存與成本錯誤會污染所有下游報表。
2. **成本評價法 v1 只做一種並凍結**：建議先選移動平均（Weighted Average）或 FIFO 其中一種，且商品一旦有庫存後不得變更評價法（如同 ERPNext 的限制）；批次別成本（landed cost 分攤）留到 v2，但「批次/效期/序號」的身分管理 v1 就要有，因為它影響有效期凍結與 FEFO 揀貨。
3. **v1 必須做但容易被忽略的三件事**：負庫存阻擋與例外核准、單據狀態機與變更審計軌跡（誰改了多少）、以及「可用量 vs 在手量」雙視圖。它們決定系統是否可信，也是內控與盤點的前提。
4. **多倉庫與調撥在 v1 採「最少可行」**：先支援多倉 + 轉庫單 + 在途（Transit）狀態 + 兩段式出庫/入庫；自動跨倉補貨路徑與 min/max 自動生成調撥（Odoo replenishment rule）可延後，等水位資料累積後再上。
5. **後做項目排序**：自動補貨建議採購單與水位提醒 → 條碼/RFID 掃碼作業 → 毛利/ABC/呆滯分析報表 → 電商多通路同步 → 生產/BOM/製造（v1 不做）。台灣在地稅務/發票與多語系也應明確列為 v2 或整合既有會計系統，而不是在 v1 自行實作。
