"""入庫 API（PRD FR-9、FR-27）。

入庫是本系統第一個會改變資料的功能，因此所有寫入都經由
``app.services.stock_service.post_grn()``，不得在此直接寫 ledger。
"""

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
    Grn,
    GrnLine,
    Item,
    Location,
    PurchaseOrder,
    PurchaseOrderLine,
    Warehouse,
)
from ..security import write_audit
from ..services.stock_service import GrnLineInput, StockError, post_grn
from .helpers import decimal_field, error, text_field

receiving_bp = Blueprint("receiving", __name__, url_prefix="/api/grn")

READ_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_ACCOUNTING)
POST_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE)


@receiving_bp.get("")
@require_roles(*READ_ROLES)
def list_grn():
    """入庫單列表（含明細、批次、位置）。"""
    limit = min(int(request.args.get("limit") or 50), 200)
    grns = db.session.scalars(select(Grn).order_by(Grn.in_date.desc(), Grn.id.desc()).limit(limit)).all()

    data = []
    for grn in grns:
        lines = db.session.scalars(select(GrnLine).where(GrnLine.grn_id == grn.id)).all()
        data.append(
            {
                "id": grn.id,
                "code": grn.code,
                "in_date": grn.in_date.isoformat() if grn.in_date else None,
                "operator_id": grn.operator_id,
                "note": grn.note,
                "lines": [
                    {
                        "id": line.id,
                        "item_id": line.item_id,
                        "item_code": _item_code(line.item_id),
                        "item_name": _item_name(line.item_id),
                        "batch_code": _batch_code(line.batch_id),
                        "location_code": _location_code(line.location_id),
                        "quantity": float(line.quantity),
                        "actual_unit_cost": float(line.actual_unit_cost),
                    }
                    for line in lines
                ],
            }
        )
    return jsonify({"data": data})


@receiving_bp.post("")
@require_roles(*POST_ROLES)
def create_grn():
    """建立入庫單並立即過帳。

    兩種來源：
    - ``purchase_order_id``：對採購單入庫（數量不得超過待入庫數量）
    - ``manual: true``：手動入庫（僅管理員，必須填原因）
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        return error("入庫單至少需要一筆明細")

    purchase_order = None
    if payload.get("purchase_order_id"):
        purchase_order = db.session.get(PurchaseOrder, payload["purchase_order_id"])
        if purchase_order is None:
            return error("找不到採購單", 404)

    reason, err = text_field(payload, "reason", max_length=200)
    if err:
        return error(err)

    manual = bool(payload.get("manual")) or purchase_order is None
    if manual and current_user().role != ROLE_ADMIN:
        return error("手動入庫僅限管理員", 403)
    if manual and not reason:
        return error("手動入庫必須填寫原因")

    parsed: list[GrnLineInput] = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            return error("明細格式錯誤")
        item_id = raw.get("item_id")
        if not item_id or db.session.get(Item, item_id) is None:
            return error("明細包含不存在的商品")
        location_id = raw.get("location_id")
        if not location_id or db.session.get(Location, location_id) is None:
            return error("明細包含不存在的庫存位置")
        quantity, err = decimal_field(raw, "quantity", minimum=Decimal("0.001"))
        if err:
            return error(err)
        if quantity is None:
            return error("入庫數量必填")
        unit_cost, err = decimal_field(raw, "unit_cost", minimum=Decimal("0"))
        if err:
            return error(err)
        if unit_cost is None:
            unit_cost = Decimal("0")
        parsed.append(
            GrnLineInput(
                item_id=item_id,
                quantity=quantity,
                unit_cost=unit_cost,
                location_id=location_id,
                purchase_order_line_id=raw.get("purchase_order_line_id"),
                note=str(raw.get("note") or "") or None,
            )
        )

    operator = current_user()
    try:
        result = post_grn(
            operator=operator,
            lines=parsed,
            purchase_order=purchase_order,
            reason=reason or None,
        )
        db.session.commit()
    except StockError as exc:
        db.session.rollback()
        return error(exc.message, exc.status)

    return (
        jsonify(
            {
                "id": result.grn.id,
                "code": result.grn.code,
                "in_date": result.grn.in_date.isoformat(),
                "batch_codes": result.batch_codes,
                "lines": len(parsed),
            }
        ),
        201,
    )


@receiving_bp.get("/locations/<int:location_id>/items")
@require_roles(*POST_ROLES)
def location_items(location_id: int):
    """位置入口入庫（FR-27）：輸入位置代碼 → 取得該位置品項與數量。

    數量以**庫存異動帳**為準（該位置目前的存量），不是入庫單明細。
    """
    from sqlalchemy import func

    from ..models import StockLedger

    location = db.session.get(Location, location_id)
    if location is None:
        return error("找不到庫存位置", 404)

    rows = db.session.execute(
        select(
            Item.id,
            Item.code,
            Item.name,
            Item.unit,
            func.sum(StockLedger.qty),
        )
        .join(StockLedger, StockLedger.item_id == Item.id)
        .where(StockLedger.location_id == location_id)
        .group_by(Item.id, Item.code, Item.name, Item.unit)
        .order_by(Item.code)
    ).all()

    warehouse = db.session.get(Warehouse, location.warehouse_id)
    return jsonify(
        {
            "location": {
                "id": location.id,
                "code": location.code,
                "name": location.name,
                "warehouse_code": warehouse.code if warehouse else None,
                "warehouse_name": warehouse.name if warehouse else None,
            },
            "items": [
                {
                    "item_id": item_id,
                    "item_code": code,
                    "item_name": name,
                    "unit": unit,
                    "on_hand": float(qty or 0),
                }
                for item_id, code, name, unit, qty in rows
            ],
        }
    )


def _item_code(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.code if item else None


def _item_name(item_id: int) -> str | None:
    item = db.session.get(Item, item_id)
    return item.name if item else None


def _batch_code(batch_id: int) -> str | None:
    from ..models import Batch

    batch = db.session.get(Batch, batch_id)
    return batch.code if batch else None


def _location_code(location_id: int) -> str | None:
    location = db.session.get(Location, location_id)
    return location.code if location else None
