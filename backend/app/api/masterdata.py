"""主檔 API（PRD FR-4、FR-8、FR-20、FR-32）。

讀取：依角色可見範圍（見 PRD §4.1 權限矩陣）。
建立：僅允許權限矩陣中標示 ✅ 的角色。
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from ..auth import require_roles
from ..extensions import db
from ..models import (
    ROLE_ADMIN,
    ROLE_ACCOUNTING,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    Customer,
    Item,
    ItemSupplier,
    Location,
    Supplier,
    Warehouse,
)
from ..security import write_audit

masterdata_bp = Blueprint("masterdata", __name__, url_prefix="/api")

# 角色 → 可讀取的主檔
READABLE_BY = {
    "items": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "suppliers": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "customers": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "warehouses": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
    "locations": (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING),
}


def _money(value) -> float:
    return float(value) if value is not None else 0.0


@masterdata_bp.get("/items")
@require_roles(*READABLE_BY["items"])
def list_items():
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit") or 50), 200)
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
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "商品名稱必填"}), 400

    code = _next_item_code()
    item = Item(
        code=code,
        name=name,
        unit=(payload.get("unit") or "PCS").strip(),
        suggested_price=_to_decimal(payload.get("suggested_price")),
        target_margin_rate=_to_decimal(payload.get("target_margin_rate")),
    )
    db.session.add(item)
    db.session.flush()
    write_audit("ITEM_CREATED", doc_type="item", doc_id=item.code, item_id=item.id, detail=item.name)
    db.session.commit()
    return jsonify({"id": item.id, "code": item.code}), 201


@masterdata_bp.get("/suppliers")
@require_roles(*READABLE_BY["suppliers"])
def list_suppliers():
    suppliers = db.session.scalars(select(Supplier).order_by(Supplier.name)).all()
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
    """採購角色看不到客戶名稱（PRD §4.1 資料可見規則）。"""
    from ..auth import current_user

    user = current_user()
    mask = user.role == ROLE_PURCHASING
    customers = db.session.scalars(select(Customer).order_by(Customer.name)).all()
    return jsonify(
        {
            "data": [
                {
                    "id": c.id,
                    "name": "（採購角色不可見）" if mask else c.name,
                    "contact": c.contact,
                    "phone": c.phone,
                }
                for c in customers
            ]
        }
    )


@masterdata_bp.get("/warehouses")
@require_roles(*READABLE_BY["warehouses"])
def list_warehouses():
    warehouses = db.session.scalars(select(Warehouse).order_by(Warehouse.code)).all()
    return jsonify(
        {
            "data": [
                {
                    "id": w.id,
                    "code": w.code,
                    "name": w.name,
                    "is_virtual": w.is_virtual,
                }
                for w in warehouses
            ]
        }
    )


@masterdata_bp.get("/locations")
@require_roles(*READABLE_BY["locations"])
def list_locations():
    stmt = (
        select(Location, Warehouse)
        .join(Warehouse, Location.warehouse_id == Warehouse.id)
        .order_by(Warehouse.code, Location.code)
    )
    rows = db.session.execute(stmt).all()
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
    """商品編號 = IT- + 6 位數字流水（PRD A11）。"""
    last = db.session.scalars(select(Item.code).order_by(Item.code.desc()).limit(1)).first()
    seq = 1
    if last and last.startswith("IT-"):
        try:
            seq = int(last[3:]) + 1
        except ValueError:
            seq = db.session.query(Item).count() + 1
    return f"IT-{seq:06d}"


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))
