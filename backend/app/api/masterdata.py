"""主檔 API（PRD FR-4、FR-8、FR-20、FR-32）。

讀取範圍依 PRD §4.1 權限矩陣；資料可見規則同節（採購看不到客戶名稱）。
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from ..auth import current_user, require_roles
from ..extensions import db
from ..models import (
    ROLE_ADMIN,
    ROLE_ACCOUNTING,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    Customer,
    Item,
    Location,
    Supplier,
    Warehouse,
)
from ..security import write_audit
from .helpers import decimal_field, error, int_arg, text_field

masterdata_bp = Blueprint("masterdata", __name__, url_prefix="/api")

# 資源 → 可讀取的角色（PRD §4.1 權限矩陣：✖ = 不可見，👁 = 唯讀）
READABLE_BY = {
    "items": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "suppliers": (ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "customers": (ROLE_ADMIN, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "warehouses": (ROLE_ADMIN, ROLE_ACCOUNTING),
    "locations": (ROLE_ADMIN, ROLE_ACCOUNTING),
}

MONEY_MAX = Decimal("99999999.99")


def _money(value) -> float:
    return round(float(value), 2) if value is not None else 0.0


@masterdata_bp.get("/items")
@require_roles(*READABLE_BY["items"])
def list_items():
    q = (request.args.get("q") or "").strip()
    limit = int_arg("limit")
    stmt = select(Item).where(Item.status == "active")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Item.name.ilike(like), Item.code.ilike(like)))
    items = db.session.scalars(stmt.order_by(Item.code).limit(limit)).all()
    return jsonify(
        {
            "data": [
                {
                    "id": i.id,
                    "code": i.code,
                    "name": i.name,
                    "unit": i.unit,
                    "suggested_price": _money(i.suggested_price),
                    "target_margin_rate": _money(i.target_margin_rate),
                }
                for i in items
            ]
        }
    )


@masterdata_bp.post("/items")
@require_roles(ROLE_ADMIN)
def create_item():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    name, err = text_field(payload, "name", required=True, max_length=200)
    if err:
        return error(err)
    unit, err = text_field(payload, "unit", max_length=20, default="PCS")
    if err:
        return error(err)
    if not unit:
        unit = "PCS"

    price, err = decimal_field(payload, "suggested_price", minimum=Decimal("0"), maximum=MONEY_MAX)
    if err:
        return error(err)
    margin, err = decimal_field(payload, "target_margin_rate", minimum=Decimal("0"), maximum=Decimal("1"))
    if err:
        return error(err)

    # 編號產生為讀取-寫入，以唯一性衝突重試處理併發
    for _ in range(3):
        item = Item(
            code=_next_item_code(),
            name=name,
            unit=unit,
            suggested_price=price,
            target_margin_rate=margin,
        )
        db.session.add(item)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            continue
        write_audit("ITEM_CREATED", doc_type="item", doc_id=item.code, item_id=item.id, detail=item.name)
        db.session.commit()
        return jsonify({"id": item.id, "code": item.code, "name": item.name}), 201

    return error("商品編號產生衝突，請重試", 409)


@masterdata_bp.get("/suppliers")
@require_roles(*READABLE_BY["suppliers"])
def list_suppliers():
    suppliers = db.session.scalars(
        select(Supplier).where(Supplier.status == "active").order_by(Supplier.name)
    ).all()
    return jsonify(
        {
            "data": [
                {
                    "id": s.id,
                    "tax_id": s.tax_id,
                    "name": s.name,
                    "contact": s.contact,
                    "phone": s.phone,
                }
                for s in suppliers
            ]
        }
    )


@masterdata_bp.get("/customers")
@require_roles(*READABLE_BY["customers"])
def list_customers():
    """採購角色看不到客戶身分（PRD §4.1：採購僅看銷貨彙總）。"""
    user = current_user()
    masked = user is not None and user.role == ROLE_PURCHASING
    customers = db.session.scalars(
        select(Customer).where(Customer.status == "active").order_by(Customer.name)
    ).all()
    if masked:
        return jsonify(
            {
                "data": [
                    {"id": c.id, "name": "（採購角色不可見）", "contact": None, "phone": None}
                    for c in customers
                ]
            }
        )
    return jsonify(
        {
            "data": [
                {"id": c.id, "name": c.name, "contact": c.contact, "phone": c.phone}
                for c in customers
            ]
        }
    )


@masterdata_bp.get("/warehouses")
@require_roles(*READABLE_BY["warehouses"])
def list_warehouses():
    warehouses = db.session.scalars(
        select(Warehouse).where(Warehouse.status == "active").order_by(Warehouse.code)
    ).all()
    return jsonify(
        {
            "data": [
                {"id": w.id, "code": w.code, "name": w.name, "is_virtual": w.is_virtual}
                for w in warehouses
            ]
        }
    )


@masterdata_bp.get("/locations")
@require_roles(*READABLE_BY["locations"])
def list_locations():
    rows = db.session.execute(
        select(Location, Warehouse)
        .join(Warehouse, Location.warehouse_id == Warehouse.id)
        .where(Location.status == "active", Warehouse.status == "active")
        .order_by(Warehouse.code, Location.code)
    ).all()
    return jsonify(
        {
            "data": [
                {
                    "id": loc.id,
                    "code": loc.code,
                    "name": loc.name,
                    "warehouse_code": wh.code,
                    "warehouse_name": wh.name,
                    "is_virtual": wh.is_virtual,
                }
                for loc, wh in rows
            ]
        }
    )


def _next_item_code() -> str:
    """商品編號 = IT- + 6 位數字流水（PRD A11）。

    取所有 ``IT-<數字>`` 編號的最大值加一；非數字後綴的編號不參與比較，
    避免字典序排序在 999999 之後錯亂。
    """
    codes = db.session.scalars(select(Item.code).where(Item.code.like("IT-%"))).all()
    numbers = [int(c[3:]) for c in codes if c[3:].isdigit()]
    return f"IT-{(max(numbers) if numbers else 0) + 1:06d}"
