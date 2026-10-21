"""庫存移轉與跨倉調貨 API（PRD FR-11、FR-18）。"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import current_user, require_roles
from ..extensions import db
from ..models import (
    ROLE_ACCOUNTING,
    ROLE_ADMIN,
    ROLE_PURCHASING,
    ROLE_WAREHOUSE,
    Batch,
    Item,
    Location,
    TransferOrder,
    TransferOrderLine,
    Warehouse,
)
from ..security import write_audit
from ..services.stock_service import (
    StockError,
    TransferLineInput,
    create_transfer,
    move_stock as move_stock_service,
    receive_transfer,
    ship_transfer,
)
from .helpers import decimal_field, error

transfer_bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")

READ_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_ACCOUNTING)
WRITE_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE)


@transfer_bp.get("/transfer-orders")
@require_roles(*READ_ROLES)
def list_transfer_orders():
    """調貨單列表（含明細、出庫／收貨狀態）。"""
    orders = db.session.scalars(
        select(TransferOrder).order_by(TransferOrder.id.desc()).limit(100)
    ).all()
    data = []
    for order in orders:
        lines = db.session.scalars(
            select(TransferOrderLine).where(TransferOrderLine.to_id == order.id)
        ).all()
        from_wh = db.session.get(Warehouse, order.from_warehouse_id)
        to_wh = db.session.get(Warehouse, order.to_warehouse_id)
        data.append(
            {
                "id": order.id,
                "code": order.code,
                "status": order.status,
                "from_warehouse_code": from_wh.code if from_wh else None,
                "from_warehouse_name": from_wh.name if from_wh else None,
                "to_warehouse_code": to_wh.code if to_wh else None,
                "to_warehouse_name": to_wh.name if to_wh else None,
                "ship_date": order.ship_date.isoformat() if order.ship_date else None,
                "receive_date": order.receive_date.isoformat() if order.receive_date else None,
                "demand_source": order.demand_source,
                "lines": [
                    {
                        "id": line.id,
                        "item_id": line.item_id,
                        "item_code": _item_code(line.item_id),
                        "item_name": _item_name(line.item_id),
                        "batch_code": _batch_code(line.batch_id),
                        "from_location_code": _location_code(line.from_location_id),
                        "quantity": float(line.quantity),
                        "received_quantity": (
                            float(line.received_quantity)
                            if line.received_quantity is not None
                            else None
                        ),
                        "shortage": (
                            float(line.quantity - line.received_quantity)
                            if line.received_quantity is not None
                            else None
                        ),
                    }
                    for line in lines
                ],
            }
        )
    return jsonify({"data": data})


@transfer_bp.post("/transfer-orders")
@require_roles(*WRITE_ROLES)
def create_transfer_order():
    """建立調貨單（草稿）。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    from_warehouse_id = payload.get("from_warehouse_id")
    to_warehouse_id = payload.get("to_warehouse_id")
    if not from_warehouse_id or not to_warehouse_id:
        return error("請指定來源倉庫與目的倉庫")

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        return error("調貨單至少需要一筆明細")

    parsed = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            return error("明細格式錯誤")
        batch_id = raw.get("batch_id")
        from_location_id = raw.get("from_location_id")
        if not batch_id or db.session.get(Batch, batch_id) is None:
            return error("明細包含不存在的批次")
        if not from_location_id or db.session.get(Location, from_location_id) is None:
            return error("明細包含不存在的庫存位置")
        quantity, err = decimal_field(raw, "quantity", minimum=Decimal("0.001"))
        if err:
            return error(err)
        if quantity is None:
            return error("調貨數量必填")
        batch = db.session.get(Batch, batch_id)
        parsed.append(
            TransferLineInput(
                item_id=batch.item_id,
                batch_id=batch_id,
                from_location_id=from_location_id,
                quantity=quantity,
            )
        )

    try:
        order = create_transfer(
            operator=current_user(),
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            lines=parsed,
            demand_source=str(payload.get("demand_source") or "") or None,
        )
        db.session.commit()
    except StockError as exc:
        db.session.rollback()
        return error(exc.message, exc.status)

    return jsonify({"id": order.id, "code": order.code, "status": order.status}), 201


@transfer_bp.post("/transfer-orders/<int:order_id>/ship")
@require_roles(*WRITE_ROLES)
def ship_transfer_order(order_id: int):
    """調貨出庫：來源倉 → 在途。"""
    order = db.session.get(TransferOrder, order_id)
    if order is None:
        return error("找不到調貨單", 404)
    try:
        ship_transfer(operator=current_user(), order=order)
        db.session.commit()
    except StockError as exc:
        db.session.rollback()
        return error(exc.message, exc.status)
    return jsonify({"id": order.id, "code": order.code, "status": order.status})


@transfer_bp.post("/transfer-orders/<int:order_id>/receive")
@require_roles(*WRITE_ROLES)
def receive_transfer_order(order_id: int):
    """調貨收貨：在途 → 目的倉位。body: {"receipts": [{"line_id": 1, "quantity": 50, "location_id": 2}]}"""
    order = db.session.get(TransferOrder, order_id)
    if order is None:
        return error("找不到調貨單", 404)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")
    raw_receipts = payload.get("receipts")
    if not isinstance(raw_receipts, list) or not raw_receipts:
        return error("請提供收貨明細")

    receipts = []
    for raw in raw_receipts:
        if not isinstance(raw, dict):
            return error("收貨明細格式錯誤")
        line_id = raw.get("line_id")
        quantity, err = decimal_field(raw, "quantity", minimum=Decimal("0"))
        if err:
            return error(err)
        if quantity is None:
            return error("收貨數量必填")
        location_id = raw.get("location_id")
        if not location_id or db.session.get(Location, location_id) is None:
            return error("收貨明細包含不存在的庫存位置")
        receipts.append((line_id, quantity, location_id))

    try:
        receive_transfer(operator=current_user(), order=order, receipts=receipts)
        db.session.commit()
    except StockError as exc:
        db.session.rollback()
        return error(exc.message, exc.status)

    return jsonify({"id": order.id, "code": order.code, "status": order.status})


@transfer_bp.post("/move")
@require_roles(*WRITE_ROLES)
def move_stock():
    """同倉移轉（FR-11）：來源庫位 → 目標庫位，總量守恆。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    batch_id = payload.get("batch_id")
    from_location_id = payload.get("from_location_id")
    to_location_id = payload.get("to_location_id")
    if not batch_id or db.session.get(Batch, batch_id) is None:
        return error("請指定有效的批次")
    if not from_location_id or not to_location_id:
        return error("請指定來源與目標庫存位置")

    quantity, err = decimal_field(payload, "quantity", minimum=Decimal("0.001"))
    if err:
        return error(err)
    if quantity is None:
        return error("移轉數量必填")

    batch = db.session.get(Batch, batch_id)
    try:
        move_stock_service(
            operator=current_user(),
            item_id=batch.item_id,
            batch_id=batch_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            quantity=quantity,
            note=str(payload.get("note") or "") or None,
        )
        db.session.commit()
    except StockError as exc:
        db.session.rollback()
        return error(exc.message, exc.status)

    return jsonify({"ok": True, "item_id": batch.item_id, "quantity": float(quantity)})


def _item_code(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.code if item else None


def _item_name(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.name if item else None


def _batch_code(batch_id: int) -> str | None:
    batch = db.session.get(Batch, batch_id)
    return batch.code if batch else None


def _location_code(location_id: int) -> str | None:
    location = db.session.get(Location, location_id)
    return location.code if location else None
