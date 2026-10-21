"""庫存查詢 API（PRD FR-6、FR-12）。

數字定義（不可簡化，見 spec Implementation Notes）：
- 在手量 on_hand  = Σ stock_balances.qty（含 TRANSIT 在途位置）
- 可用量 available = on_hand − Σ allocations.qty（status=active）
- 在途量 in_transit = Σ stock_balances.qty where 該位置屬於虛擬倉（TRANSIT）
- 實體倉合計 real_on_hand = on_hand − in_transit
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from ..auth import require_roles
from ..extensions import db
from ..models import (
    ROLE_ACCOUNTING,
    ROLE_ADMIN,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    Allocation,
    Batch,
    Item,
    Location,
    StockBalance,
    Warehouse,
)

stock_bp = Blueprint("stock", __name__, url_prefix="/api/stock")

READ_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING)


@stock_bp.get("/query")
@require_roles(*READ_ROLES)
def query_stock():
    """依商品名稱或編號查詢庫存（FR-6、FR-12）。結果上限 50 筆。"""
    q = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit") or 50), 200)

    stmt = select(Item).where(Item.status == "active")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Item.name.ilike(like), Item.code.ilike(like)))
    items = db.session.scalars(stmt.order_by(Item.code).limit(limit)).all()
    item_ids = [i.id for i in items]

    if not item_ids:
        return jsonify({"data": [], "total": 0})

    # 餘額（含位置與倉庫資訊）
    rows = db.session.execute(
        select(StockBalance, Location, Warehouse, Batch)
        .join(Location, StockBalance.location_id == Location.id)
        .join(Warehouse, Location.warehouse_id == Warehouse.id)
        .join(Batch, StockBalance.batch_id == Batch.id)
        .where(StockBalance.item_id.in_(item_ids))
    ).all()

    # 配置量
    alloc_rows = db.session.execute(
        select(Allocation.item_id, Allocation.batch_id, Allocation.location_id, Allocation.qty)
        .where(Allocation.item_id.in_(item_ids), Allocation.status == "active")
    ).all()

    alloc_map: dict[tuple[int, int, int], Decimal] = {}
    for item_id, batch_id, location_id, qty in alloc_rows:
        key = (item_id, batch_id, location_id)
        alloc_map[key] = alloc_map.get(key, Decimal("0")) + Decimal(str(qty))

    per_item: dict[int, dict] = {
        i.id: {
            "item": i,
            "on_hand": Decimal("0"),
            "available": Decimal("0"),
            "in_transit": Decimal("0"),
            "locations": [],
        }
        for i in items
    }

    for balance, location, warehouse, batch in rows:
        bucket = per_item[balance.item_id]
        qty = Decimal(str(balance.qty))
        allocated = alloc_map.get((balance.item_id, balance.batch_id, balance.location_id), Decimal("0"))

        bucket["on_hand"] += qty
        bucket["available"] += qty - allocated
        if warehouse.is_virtual:
            bucket["in_transit"] += qty

        bucket["locations"].append(
            {
                "warehouse_code": warehouse.code,
                "warehouse_name": warehouse.name,
                "is_virtual": warehouse.is_virtual,
                "location_code": location.code,
                "location_name": location.name,
                "batch_code": batch.code,
                "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                "on_hand": _f(qty),
                "allocated": _f(allocated),
                "available": _f(qty - allocated),
            }
        )

    data = []
    for bucket in per_item.values():
        item = bucket["item"]
        data.append(
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "suggested_price": _f(item.suggested_price),
                "on_hand": _f(bucket["on_hand"]),
                "available": _f(bucket["available"]),
                "in_transit": _f(bucket["in_transit"]),
                "real_on_hand": _f(bucket["on_hand"] - bucket["in_transit"]),
                "locations": sorted(
                    bucket["locations"],
                    key=lambda x: (x["warehouse_code"], x["location_code"], x["batch_code"]),
                ),
            }
        )

    # 依商品層級可用量合計由大到小排序（FR-12）
    data.sort(key=lambda x: (-x["available"], x["code"]))

    return jsonify({"data": data, "total": len(data)})


@stock_bp.get("/items/<int:item_id>/batches")
@require_roles(*READ_ROLES)
def item_batches(item_id: int):
    """某商品的批次明細與成本（FR-5、FR-6）。"""
    item = db.session.get(Item, item_id)
    if item is None:
        return jsonify({"error": "找不到商品"}), 404

    rows = db.session.execute(
        select(Batch, StockBalance, Location, Warehouse)
        .join(StockBalance, StockBalance.batch_id == Batch.id)
        .join(Location, StockBalance.location_id == Location.id)
        .join(Warehouse, Location.warehouse_id == Warehouse.id)
        .where(Batch.item_id == item_id)
        .order_by(Batch.in_date, Batch.code)
    ).all()

    return jsonify(
        {
            "item": {"id": item.id, "code": item.code, "name": item.name},
            "data": [
                {
                    "batch_code": batch.code,
                    "in_date": batch.in_date.isoformat(),
                    "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                    "actual_unit_cost": _f(batch.actual_unit_cost),
                    "warehouse_code": wh.code,
                    "location_code": loc.code,
                    "is_virtual": wh.is_virtual,
                    "on_hand": _f(balance.qty),
                }
                for batch, balance, loc, wh in rows
            ],
        }
    )


def _f(value) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)))
