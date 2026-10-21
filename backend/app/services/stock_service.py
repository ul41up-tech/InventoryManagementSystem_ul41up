"""庫存寫入服務層——**唯一的庫存異動入口**。

PRD §1 的主張是「商品 → 單據 → 餘額 → 成本 → 毛利」這條主線必須對得上。
要成立，所有庫存異動都必須經過同一個入口，才能保證：

1. `stock_ledger`（異動帳）是唯一事實來源；`stock_balances` 只是快取。
2. 批次、ledger、餘額、稽核紀錄在**同一個資料庫交易**內完成，失敗整筆回滾。
3. 餘額列以列鎖（``SELECT ... FOR UPDATE``）保護，避免併發超賣。
4. 任何異動都不得使可用量為負（FR-31）。
5. 任何異動都留下不可刪除的稽核紀錄（FR-3）。

**其他切片不得繞過本模組直接寫 ``stock_ledger``。**
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select

from ..extensions import db
from ..models import (
    MOVE_GRN,
    Allocation,
    Batch,
    Grn,
    GrnLine,
    Item,
    Location,
    PurchaseOrder,
    PurchaseOrderLine,
    StockBalance,
    StockLedger,
    User,
)
from ..security import write_audit

ZERO = Decimal("0")


class StockError(Exception):
    """庫存業務錯誤（回傳 400）。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class GrnLineInput:
    """一筆入庫明細。"""

    item_id: int
    quantity: Decimal
    unit_cost: Decimal
    location_id: int
    purchase_order_line_id: int | None = None
    note: str | None = None


@dataclass
class PostGrnResult:
    grn: Grn
    batch_codes: list[str] = field(default_factory=list)


def _next_daily_code(day: str, existing: list[str], width: int = 3) -> str:
    """依當日已存在的編號產生下一個流水號。"""
    numbers = [int(code[len(day):]) for code in existing if code[len(day):].isdigit()]
    return f"{day}{(max(numbers) if numbers else 0) + 1:0{width}d}"


def next_batch_code(date: dt.date) -> str:
    """批次編號：B-YYYYMMDD-NNN（PRD FR-5）。"""
    day = f"B{date:%Y%m%d}-"
    rows = db.session.execute(
        select(Batch.code).where(Batch.code.like(f"{day}%"))
    ).scalars().all()
    return _next_daily_code(day, list(rows))


def next_grn_code(date: dt.date) -> str:
    """入庫單編號：GR-YYYYMMDD-NNN。"""
    day = f"GR-{date:%Y%m%d}-"
    rows = db.session.execute(
        select(Grn.code).where(Grn.code.like(f"{day}%"))
    ).scalars().all()
    return _next_daily_code(day, list(rows))


def next_po_code(date: dt.date) -> str:
    """採購單編號：PO-YYYYMMDD-NNN（PRD FR-23）。"""
    day = f"PO-{date:%Y%m%d}-"
    rows = db.session.execute(
        select(PurchaseOrder.code).where(PurchaseOrder.code.like(f"{day}%"))
    ).scalars().all()
    return _next_daily_code(day, list(rows))


def _lock_balance(item_id: int, batch_id: int, location_id: int) -> StockBalance:
    """取得（必要時建立）餘額列並對其加列鎖。"""
    stmt = (
        select(StockBalance)
        .where(
            StockBalance.item_id == item_id,
            StockBalance.batch_id == batch_id,
            StockBalance.location_id == location_id,
        )
        .with_for_update()
    )
    row = db.session.execute(stmt).scalar_one_or_none()
    if row is None:
        row = StockBalance(item_id=item_id, batch_id=batch_id, location_id=location_id, qty=ZERO)
        db.session.add(row)
        db.session.flush()
    return row


def apply_stock_change(
    *,
    item_id: int,
    batch_id: int,
    location_id: int,
    qty: Decimal,
    move_type: str,
    operator: User | None,
    source_type: str | None = None,
    source_id: int | None = None,
    note: str | None = None,
) -> StockBalance:
    """套用一筆庫存異動：寫 ledger 並同步快取。呼叫端必須已在交易中。"""
    balance = _lock_balance(item_id, batch_id, location_id)
    new_qty = Decimal(str(balance.qty or 0)) + qty
    if new_qty < 0:
        db.session.rollback()
        raise StockError("此異動會使庫存數量為負，已拒絕")
    balance.qty = new_qty
    db.session.add(
        StockLedger(
            item_id=item_id,
            batch_id=batch_id,
            location_id=location_id,
            qty=qty,
            move_type=move_type,
            source_type=source_type,
            source_id=source_id,
            operator_id=operator.id if operator else None,
            note=note,
        )
    )
    return balance


def assert_available_non_negative(item_id: int) -> None:
    """全域負庫存防護（FR-31）：可用量 = 在手量 − 有效配置量，不得為負。"""
    on_hand = db.session.execute(
        select(StockBalance.qty).where(StockBalance.item_id == item_id)
    ).scalars().all()
    total_on_hand = sum((Decimal(str(q or 0)) for q in on_hand), ZERO)
    allocated = db.session.execute(
        select(Allocation.qty).where(
            Allocation.item_id == item_id, Allocation.status == "active"
        )
    ).scalars().all()
    total_allocated = sum((Decimal(str(q or 0)) for q in allocated), ZERO)
    if total_on_hand - total_allocated < 0:
        db.session.rollback()
        raise StockError(
            "此異動會使可用量為負（在手量 "
            f"{total_on_hand} − 已配置 {total_allocated}），已拒絕"
        )


def _validate_lines(lines: list[GrnLineInput]) -> None:
    if not lines:
        raise StockError("入庫單至少需要一筆明細")
    for line in lines:
        if line.quantity <= 0:
            raise StockError("入庫數量必須大於 0")
        if line.unit_cost < 0:
            raise StockError("實際入庫單價不可為負")
        if db.session.get(Item, line.item_id) is None:
            raise StockError("找不到商品")
        if db.session.get(Location, line.location_id) is None:
            raise StockError("找不到庫存位置")


def _validate_pending_quantities(
    lines: list[GrnLineInput], purchase_order: PurchaseOrder
) -> None:
    """入庫數量不得超過採購單行的待入庫數量（FR-9、FR-23）。"""
    for line in lines:
        if line.purchase_order_line_id is None:
            continue
        po_line = db.session.get(PurchaseOrderLine, line.purchase_order_line_id)
        if po_line is None or po_line.po_id != purchase_order.id:
            raise StockError("採購單明細與入庫單不符")
        received = received_quantity(po_line)
        pending = Decimal(str(po_line.quantity)) - received
        if line.quantity > pending:
            raise StockError(
                f"入庫數量 {line.quantity} 超過待入庫數量 {pending}"
                f"（商品 {po_line.item_id}，訂購數量 {po_line.quantity}）"
            )


def received_quantity(po_line: PurchaseOrderLine) -> Decimal:
    """某採購單行已入庫數量（由入庫單明細加總）。"""
    rows = db.session.execute(
        select(GrnLine.quantity)
        .join(Grn, GrnLine.grn_id == Grn.id)
        .where(GrnLine.purchase_order_line_id == po_line.id)
    ).scalars().all()
    return sum((Decimal(str(q or 0)) for q in rows), ZERO)


def pending_quantity(po_line: PurchaseOrderLine) -> Decimal:
    """待入庫數量 = 訂購數量 − 已入庫數量。"""
    return Decimal(str(po_line.quantity)) - received_quantity(po_line)


def post_grn(
    *,
    operator: User,
    lines: list[GrnLineInput],
    purchase_order: PurchaseOrder | None = None,
    reason: str | None = None,
    in_date: dt.date | None = None,
) -> PostGrnResult:
    """建立入庫單並**立即過帳**（建立即過帳，之後不可修改）。

    同一交易內完成：入庫單 → 批次 → 庫存異動帳 → 餘額快取 → 稽核紀錄。
    """
    _validate_lines(lines)

    if purchase_order is not None:
        _validate_pending_quantities(lines, purchase_order)
    elif not reason:
        # 手動入庫（無採購單）必須說明原因
        raise StockError("手動入庫必須填寫原因")

    today = in_date or dt.date.today()
    grn = Grn(
        code=next_grn_code(today),
        supplier_id=purchase_order.supplier_id if purchase_order else None,
        operator_id=operator.id,
        in_date=today,
        note=reason,
    )
    db.session.add(grn)
    db.session.flush()

    batch_codes: list[str] = []

    for line in lines:
        batch = Batch(
            code=next_batch_code(today),
            item_id=line.item_id,
            purchase_order_id=purchase_order.id if purchase_order else None,
            supplier_id=purchase_order.supplier_id if purchase_order else None,
            actual_unit_cost=line.unit_cost,
            quantity=line.quantity,
            in_date=today,
        )
        db.session.add(batch)
        db.session.flush()
        batch_codes.append(batch.code)

        grn_line = GrnLine(
            grn_id=grn.id,
            item_id=line.item_id,
            batch_id=batch.id,
            location_id=line.location_id,
            quantity=line.quantity,
            actual_unit_cost=line.unit_cost,
            purchase_order_line_id=line.purchase_order_line_id,
            note=line.note,
        )
        db.session.add(grn_line)
        db.session.flush()

        apply_stock_change(
            item_id=line.item_id,
            batch_id=batch.id,
            location_id=line.location_id,
            qty=line.quantity,
            move_type=MOVE_GRN,
            operator=operator,
            source_type="GRN",
            source_id=grn.id,
            note=f"入庫單 {grn.code}",
        )
        assert_available_non_negative(line.item_id)

        write_audit(
            "GRN_POSTED",
            operator=operator,
            doc_type="grn",
            doc_id=grn.code,
            item_id=line.item_id,
            batch_id=batch.id,
            location_id=line.location_id,
            qty=line.quantity,
            reason=reason,
            detail=f"批次 {batch.code}，實際單價 {line.unit_cost}",
        )

    db.session.flush()
    return PostGrnResult(grn=grn, batch_codes=batch_codes)
