"""資料模型。

對應 PRD addendum §1.4 的資料模型。**改動此檔等同改 schema，必須同步產生 migration。**

數量欄位一律使用 Numeric(14, 3)（可小數），金額使用 Numeric(12, 2)。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db
from .timeutil import utcnow

# --- 角色常數（PRD §3「角色」，v1 固定五種）---
ROLE_ADMIN = "admin"
ROLE_WAREHOUSE = "warehouse"
ROLE_PURCHASING = "purchasing"
ROLE_SALES = "sales"
ROLE_ACCOUNTING = "accounting"
ALL_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING)

# --- 異動類型（stock_ledger.move_type）---
MOVE_GRN = "GRN"  # 入庫
MOVE_ISSUE = "ISSUE"  # 出庫（領用）
MOVE_TRANSFER_OUT = "TRANSFER_OUT"  # 移出（→ 在途）
MOVE_TRANSFER_IN = "TRANSFER_IN"  # 移入（自 在途）
MOVE_ADJUST = "ADJUST"  # 盤盈／盤虧／報廢


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class User(TimestampMixin, db.Model):
    """使用者帳號。v1 以單一 role 欄位表達權限群組（PRD A8）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_WAREHOUSE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} role={self.role}>"


class Item(TimestampMixin, db.Model):
    """商品主檔（PRD FR-4）。"""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), default="PCS", nullable=False)
    suggested_price: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    target_margin_rate: Mapped[Numeric | None] = mapped_column(Numeric(6, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    suppliers: Mapped[list["ItemSupplier"]] = relationship(back_populates="item")


class Supplier(TimestampMixin, db.Model):
    """供應商（PRD FR-20）。"""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class ItemSupplier(db.Model):
    """商品 × 供應商（多對多），含主供應商旗標（PRD FR-22）。"""

    __tablename__ = "item_suppliers"
    __table_args__ = (UniqueConstraint("item_id", "supplier_id", name="uq_item_supplier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    item: Mapped[Item] = relationship(back_populates="suppliers")
    supplier: Mapped[Supplier] = relationship()


class Customer(TimestampMixin, db.Model):
    """最小客戶主檔（PRD FR-32）。"""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class Warehouse(TimestampMixin, db.Model):
    """倉庫。TRANSIT 為虛擬在途位置（is_virtual=True），不屬於任何實體倉。"""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class Location(TimestampMixin, db.Model):
    """庫存位置（PRD FR-8）。"""

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("code", "warehouse_id", name="uq_location_code_per_warehouse"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    warehouse: Mapped[Warehouse] = relationship()


class PurchaseOrder(TimestampMixin, db.Model):
    """採購單（PRD FR-23）。單價為預估，不構成成本依據。"""

    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    order_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, nullable=False)
    expected_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PurchaseOrderLine(db.Model):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    total_price: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)


class Grn(TimestampMixin, db.Model):
    """入庫單（PRD FR-9）。過帳時建立批次。"""

    __tablename__ = "grn"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    in_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class GrnLine(db.Model):
    __tablename__ = "grn_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("grn.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    actual_unit_cost: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    purchase_order_line_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_order_lines.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Batch(TimestampMixin, db.Model):
    """批次（PRD FR-5）。於入庫單過帳時建立。"""

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    actual_unit_cost: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    in_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


class SalesOrder(TimestampMixin, db.Model):
    """銷貨單（PRD FR-14）。收入與毛利的唯一認列來源。"""

    __tablename__ = "sales_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    salesperson_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    order_date: Mapped[dt.date] = mapped_column(Date, default=dt.date.today, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    discount_value: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesOrderLine(db.Model):
    """銷貨單明細。cost_snapshot 為過帳時的成本快照（PRD FR-17）。"""

    __tablename__ = "sales_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    so_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    net_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cost_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cost_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)


class ShippingOrder(TimestampMixin, db.Model):
    """寄貨單（PRD FR-28）。"""

    __tablename__ = "shipping_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    ship_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ShippingOrderLine(db.Model):
    __tablename__ = "shipping_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    sh_id: Mapped[int] = mapped_column(ForeignKey("shipping_orders.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)


class TransferOrder(TimestampMixin, db.Model):
    """調貨單（PRD FR-11、FR-18）。"""

    __tablename__ = "transfer_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    ship_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    receive_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    demand_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class TransferOrderLine(db.Model):
    __tablename__ = "transfer_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("transfer_orders.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)


class ReturnOrder(TimestampMixin, db.Model):
    """反向單據（PRD FR-29）。"""

    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class StockAdjustment(TimestampMixin, db.Model):
    """調整單（PRD FR-30）：報廢、盤點差異、調貨短缺、內部領用。"""

    __tablename__ = "stock_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    adjust_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class StockAdjustmentLine(db.Model):
    __tablename__ = "stock_adjustment_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    adj_id: Mapped[int] = mapped_column(ForeignKey("stock_adjustments.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)  # 正=增加, 負=減少
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Stocktake(TimestampMixin, db.Model):
    """盤點（PRD FR-13）。基準為盤點開始時點的帳面。"""

    __tablename__ = "stocktakes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class StocktakeLine(db.Model):
    __tablename__ = "stocktake_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    stocktake_id: Mapped[int] = mapped_column(ForeignKey("stocktakes.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    book_qty: Mapped[Numeric] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    counted_qty: Mapped[Numeric | None] = mapped_column(Numeric(14, 3), nullable=True)
    diff_qty: Mapped[Numeric | None] = mapped_column(Numeric(14, 3), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)


class StockLedger(db.Model):
    """庫存異動帳：在手量的唯一來源。配置量不寫入本表（PRD §3）。"""

    __tablename__ = "stock_ledger"
    __table_args__ = (
        Index("ix_ledger_item_location", "item_id", "location_id"),
        Index("ix_ledger_batch", "batch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    qty: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)  # 有正負號
    move_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class StockBalance(db.Model):
    """庫存餘額快取：由 stock_ledger 推導，可整表重建。不含可用量。"""

    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("item_id", "batch_id", "location_id", name="uq_balance_item_batch_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    qty: Mapped[Numeric] = mapped_column(Numeric(14, 3), default=0, nullable=False)


class Allocation(db.Model):
    """配置量（PRD §3）：銷貨／寄貨過帳時建立、領用時解除。跨倉調貨不建配置。"""

    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)  # SO / SH
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_line_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    qty: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active / released


class CostConsumption(db.Model):
    """成本取用明細（PRD FR-17）：每次出貨取用哪個批次、多少數量、多少成本。"""

    __tablename__ = "cost_consumptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_line_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False)
    qty: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)


class AuditLog(db.Model):
    """操作紀錄（PRD FR-3）：不可刪除。"""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    doc_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    qty: Mapped[Numeric | None] = mapped_column(Numeric(14, 3), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ReorderPoint(db.Model):
    """安全庫存水位（PRD FR-21）：以「商品 × 倉庫」為單位。"""

    __tablename__ = "reorder_points"
    __table_args__ = (UniqueConstraint("item_id", "warehouse_id", name="uq_reorder_item_warehouse"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    reorder_point: Mapped[Numeric] = mapped_column(Numeric(14, 3), nullable=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_qty: Mapped[Numeric | None] = mapped_column(Numeric(14, 3), nullable=True)
    pack_multiple: Mapped[Numeric | None] = mapped_column(Numeric(14, 3), nullable=True)
