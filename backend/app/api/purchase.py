"""採購單 API（PRD FR-23 的最小可用部分）。

本切片只提供「建立草稿採購單」與「查詢（含待入庫數量）」；
狀態機、水位警示、結案屬切片 5。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..auth import require_roles
from ..extensions import db
from ..models import (
    ROLE_ACCOUNTING,
    ROLE_ADMIN,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    Item,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)
from ..security import write_audit
from ..services.stock_service import next_po_code, pending_quantity, received_quantity
from .helpers import decimal_field, error, text_field

purchase_bp = Blueprint("purchase", __name__, url_prefix="/api/purchase-orders")

READ_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING)
WRITE_ROLES = (ROLE_ADMIN, ROLE_PURCHASING)


@purchase_bp.get("")
@require_roles(*READ_ROLES)
def list_purchase_orders():
    """採購單列表（含每行的已入庫與待入庫數量）。"""
    orders = db.session.scalars(
        select(PurchaseOrder).order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
    ).all()

    data = []
    for po in orders:
        lines = db.session.scalars(
            select(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po.id)
        ).all()
        supplier = db.session.get(Supplier, po.supplier_id)
        data.append(
            {
                "id": po.id,
                "code": po.code,
                "supplier_id": po.supplier_id,
                "supplier_name": supplier.name if supplier else None,
                "status": po.status,
                "order_date": po.order_date.isoformat() if po.order_date else None,
                "expected_date": po.expected_date.isoformat() if po.expected_date else None,
                "note": po.note,
                "lines": [
                    {
                        "id": line.id,
                        "item_id": line.item_id,
                        "item_code": _item_code(line.item_id),
                        "item_name": _item_name(line.item_id),
                        "quantity": float(line.quantity),
                        "unit_price": float(line.unit_price),
                        "total_price": float(line.total_price),
                        "received_quantity": float(received_quantity(line)),
                        "pending_quantity": float(pending_quantity(line)),
                    }
                    for line in lines
                ],
            }
        )
    return jsonify({"data": data})


@purchase_bp.post("")
@require_roles(*WRITE_ROLES)
def create_purchase_order():
    """建立草稿採購單（未送出）。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    supplier_id = payload.get("supplier_id")
    if not supplier_id or db.session.get(Supplier, supplier_id) is None:
        return error("請指定有效的供應商")

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        return error("採購單至少需要一筆明細")

    parsed = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            return error("明細格式錯誤")
        item_id = raw.get("item_id")
        if not item_id or db.session.get(Item, item_id) is None:
            return error("明細包含不存在的商品")
        quantity, err = decimal_field(raw, "quantity", minimum=Decimal("0.001"))
        if err:
            return error(err)
        if quantity is None:
            return error("明細數量必填")
        unit_price, err = decimal_field(raw, "unit_price", minimum=Decimal("0"))
        if err:
            return error(err)
        if unit_price is None:
            unit_price = Decimal("0")
        parsed.append((item_id, quantity, unit_price))

    expected_date = None
    if payload.get("expected_date"):
        try:
            expected_date = dt.date.fromisoformat(str(payload["expected_date"]))
        except ValueError:
            return error("expected_date 格式應為 YYYY-MM-DD")

    po = PurchaseOrder(
        code=next_po_code(dt.date.today()),
        supplier_id=supplier_id,
        status="draft",
        order_date=dt.date.today(),
        expected_date=expected_date,
        note=str(payload.get("note") or "") or None,
    )
    db.session.add(po)
    db.session.flush()

    for item_id, quantity, unit_price in parsed:
        db.session.add(
            PurchaseOrderLine(
                po_id=po.id,
                item_id=item_id,
                quantity=quantity,
                unit_price=unit_price,
                total_price=quantity * unit_price,
            )
        )

    write_audit("PO_CREATED", doc_type="purchase_order", doc_id=po.code, detail=f"{len(parsed)} 筆明細")
    db.session.commit()
    return jsonify({"id": po.id, "code": po.code, "status": po.status}), 201


def _item_code(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.code if item else None


def _item_name(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.name if item else None

