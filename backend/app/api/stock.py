"""庫存查詢 API（PRD FR-6、FR-12）。

數字定義（不可簡化，見 spec Implementation Notes）：
- 在手量 on_hand  = Σ stock_ledger.qty（含 TRANSIT 在途位置）。**ledger 為唯一來源**；
                    stock_balances 僅為快取，兩者差額以 balance_diff 回傳供自我檢查。
- 可用量 available = Σ max(0, 批次位置餘額 − 該位置配置量)；配置量以 allocations 為準，
                    且**沒有對應餘額的配置仍會扣減**（避免可用量被高估）。
- 在途量 in_transit = 位於虛擬在途位置（warehouse.is_virtual = True）的餘額。
- 實體倉合計 real_on_hand = on_hand − in_transit。
"""

from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

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
    StockLedger,
    Warehouse,
)
from .helpers import STOCK_QUERY_MAX_LIMIT, int_arg

stock_bp = Blueprint("stock", __name__, url_prefix="/api/stock")

READ_ROLES = (ROLE_ADMIN, ROLE_WAREHOUSE, ROLE_PURCHASING, ROLE_SALES, ROLE_ACCOUNTING)


@stock_bp.get("/query")
@require_roles(*READ_ROLES)
def query_stock():
    """依商品名稱或編號查詢庫存（FR-6、FR-12）。結果上限 50 筆（limit 可調，上限 200）。"""
    q = (request.args.get("q") or "").strip()
    limit = int_arg("limit", default=50, maximum=STOCK_QUERY_MAX_LIMIT)

    stmt = select(Item).where(Item.status == "active")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Item.name.ilike(like), Item.code.ilike(like)))

    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.session.scalars(stmt.order_by(Item.code).limit(limit)).all()
    item_ids = [i.id for i in items]

    if not item_ids:
        return jsonify({"data": [], "total": total})

    # --- 以 ledger 為準的餘額（item × batch × location）---
    ledger_rows = db.session.execute(
        select(
            StockLedger.item_id,
            StockLedger.batch_id,
            StockLedger.location_id,
            func.sum(StockLedger.qty),
        )
        .where(StockLedger.item_id.in_(item_ids))
        .group_by(StockLedger.item_id, StockLedger.batch_id, StockLedger.location_id)
    ).all()
    ledger_map = {
        (item_id, batch_id, location_id): Decimal(str(qty or 0))
        for item_id, batch_id, location_id, qty in ledger_rows
    }

    # --- 快取餘額（僅供對帳 diff）---
    balance_rows = db.session.execute(
        select(
            StockBalance.item_id,
            StockBalance.batch_id,
            StockBalance.location_id,
            func.sum(StockBalance.qty),
        )
        .where(StockBalance.item_id.in_(item_ids))
        .group_by(StockBalance.item_id, StockBalance.batch_id, StockBalance.location_id)
    ).all()
    balance_map = {
        (item_id, batch_id, location_id): Decimal(str(qty or 0))
        for item_id, batch_id, location_id, qty in balance_rows
    }

    # --- 配置量（僅 active）---
    alloc_rows = db.session.execute(
        select(
            Allocation.item_id,
            Allocation.batch_id,
            Allocation.location_id,
            func.sum(Allocation.qty),
        )
        .where(Allocation.item_id.in_(item_ids), Allocation.status == "active")
        .group_by(Allocation.item_id, Allocation.batch_id, Allocation.location_id)
    ).all()
    alloc_map = {
        (item_id, batch_id, location_id): Decimal(str(qty or 0))
        for item_id, batch_id, location_id, qty in alloc_rows
    }

    # --- 位置 / 倉庫 / 批次資訊 ---
    location_meta = {
        loc.id: (loc, wh)
        for loc, wh in db.session.execute(
            select(Location, Warehouse)
            .join(Warehouse, Location.warehouse_id == Warehouse.id)
            .where(Location.id.in_({key[2] for key in ledger_map}))
        ).all()
    }
    batch_meta = {
        b.id: b
        for b in db.session.scalars(
            select(Batch).where(Batch.id.in_({key[1] for key in ledger_map}))
        ).all()
    }

    per_item: dict[int, dict] = {
        i.id: {
            "item": i,
            "on_hand": Decimal("0"),
            "alloc_total": Decimal("0"),
            "in_transit": Decimal("0"),
            "balance_diff": Decimal("0"),
            "locations": [],
        }
        for i in items
    }

    all_keys = set(ledger_map) | set(balance_map) | set(alloc_map)
    for key in sorted(all_keys, key=lambda k: (k[0], k[1], k[2])):
        item_id, batch_id, location_id = key
        if item_id not in per_item:
            continue
        bucket = per_item[item_id]
        ledger_qty = ledger_map.get(key, Decimal("0"))
        balance_qty = balance_map.get(key, Decimal("0"))
        allocated = alloc_map.get(key, Decimal("0"))
        available = max(Decimal("0"), ledger_qty - allocated)

        bucket["on_hand"] += ledger_qty
        bucket["alloc_total"] += allocated
        bucket["balance_diff"] += ledger_qty - balance_qty

        location, warehouse = location_meta.get(location_id, (None, None))
        if warehouse is not None and warehouse.is_virtual:
            bucket["in_transit"] += ledger_qty

        batch = batch_meta.get(batch_id)
        bucket["locations"].append(
            {
                "warehouse_code": warehouse.code if warehouse else None,
                "warehouse_name": warehouse.name if warehouse else None,
                "is_virtual": warehouse.is_virtual if warehouse else False,
                "location_code": location.code if location else None,
                "location_name": location.name if location else None,
                "batch_code": batch.code if batch else None,
                "expiry_date": batch.expiry_date.isoformat()
                if batch and batch.expiry_date
                else None,
                "on_hand": _f(ledger_qty),
                "allocated": _f(allocated),
                "available": _f(available),
            }
        )

    data = []
    for bucket in per_item.values():
        item = bucket["item"]
        # 可用量 = 在手量 − 該商品所有有效配置量（沒有對應餘額的配置也要扣）
        available = max(Decimal("0"), bucket["on_hand"] - bucket["alloc_total"])
        data.append(
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "suggested_price": _f(item.suggested_price),
                "on_hand": _f(bucket["on_hand"]),
                "available": _f(available),
                "allocated": _f(bucket["alloc_total"]),
                "in_transit": _f(bucket["in_transit"]),
                "real_on_hand": _f(bucket["on_hand"] - bucket["in_transit"]),
                "balance_diff": _f(bucket["balance_diff"]),
                "locations": sorted(
                    bucket["locations"],
                    key=lambda x: (
                        str(x["warehouse_code"]),
                        str(x["location_code"]),
                        str(x["batch_code"]),
                    ),
                ),
            }
        )

    # 依商品層級可用量合計由大到小排序（FR-12）
    data.sort(key=lambda x: (-x["available"], x["code"]))

    return jsonify({"data": data, "total": total, "limit": limit})


@stock_bp.get("/items/<int:item_id>/batches")
@require_roles(*READ_ROLES)
def item_batches(item_id: int):
    """某商品的批次明細與成本（FR-5、FR-6）。"""
    item = db.session.get(Item, item_id)
    if item is None or item.status != "active":
        return jsonify({"error": "找不到商品"}), 404

    limit = int_arg("limit", default=200, maximum=500)
    rows = db.session.execute(
        select(Batch, StockLedger, Location, Warehouse)
        .join(StockLedger, StockLedger.batch_id == Batch.id)
        .join(Location, StockLedger.location_id == Location.id)
        .join(Warehouse, Location.warehouse_id == Warehouse.id)
        .where(Batch.item_id == item_id)
        .order_by(Batch.in_date, Batch.code)
        .limit(limit)
    ).all()

    return jsonify(
        {
            "item": {"id": item.id, "code": item.code, "name": item.name},
            "data": [
                {
                    "batch_code": batch.code,
                    "in_date": batch.in_date.isoformat() if batch.in_date else None,
                    "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
                    "actual_unit_cost": _f(batch.actual_unit_cost),
                    "warehouse_code": wh.code,
                    "location_code": loc.code,
                    "is_virtual": wh.is_virtual,
                    "on_hand": _f(ledger.qty),
                }
                for batch, ledger, loc, wh in rows
            ],
        }
    )


def _f(value) -> float:
    if value is None:
        return 0.0
    return round(float(Decimal(str(value))), 2)
