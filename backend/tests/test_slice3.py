"""切片 3 驗收測試：庫存移轉與跨倉調貨。

對應 spec：`_bmad-output/implementation-artifacts/spec-mvp-slice-3-移轉與調貨.md`
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.models import AuditLog, Batch, Item, Location, StockBalance, StockLedger, Warehouse
from conftest import login


def _ids(code: str = "A-01"):
    """回傳 (item_id, batch_id, location_id, warehouse_id)。"""
    loc = db.session.query(Location).filter_by(code=code).join(Location.warehouse).first()
    warehouse = db.session.get(Warehouse, loc.warehouse_id)
    item = db.session.query(Item).filter_by(code="IT-000001").first()
    # 取「確實存放在該庫位」的批次（同一商品可能有多個批次分散在不同位置）
    row = (
        db.session.query(Batch)
        .join(StockBalance, StockBalance.batch_id == Batch.id)
        .filter(Batch.item_id == item.id, StockBalance.location_id == loc.id)
        .filter(StockBalance.qty > 0)
        .first()
    )
    batch = row if row is not None else db.session.query(Batch).filter_by(item_id=item.id).first()
    return item.id, batch.id, loc.id, warehouse.id


def _on_hand(client, item_code="IT-000001") -> float:
    return client.get(f"/api/stock/query?q={item_code}").get_json()["data"][0]["on_hand"]


def _location_on_hand(client, item_code, location_code) -> float:
    rows = client.get(f"/api/stock/query?q={item_code}").get_json()["data"][0]["locations"]
    return sum(loc["on_hand"] for loc in rows if loc["location_code"] == location_code)


@pytest.fixture()
def warehouses(client, seeded):
    """回傳 (南港倉 id, 中港倉 id)。"""
    login(client, "warehouse")
    rows = client.get("/api/warehouses").get_json()["data"]
    nh = next(w for w in rows if w["code"] == "WH-NH")
    kh = next(w for w in rows if w["code"] == "WH-KH")
    return nh["id"], kh["id"]


# --- AC-1 同倉移轉 ---
def test_move_within_same_warehouse_keeps_total(client, seeded):
    login(client, "warehouse")
    item_id, batch_id, from_loc, _ = _ids("A-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-02" and loc["warehouse_code"] == "WH-NH"
    )

    before_total = _on_hand(client)
    before_from = _location_on_hand(client, "IT-000001", "A-01")
    before_to = _location_on_hand(client, "IT-000001", "A-02")

    res = client.post(
        "/api/transfers/move",
        json={
            "batch_id": batch_id,
            "from_location_id": from_loc,
            "to_location_id": to_loc,
            "quantity": 30,
        },
    )
    assert res.status_code == 200, res.get_json()

    assert _on_hand(client) == before_total  # 總量守恆
    assert _location_on_hand(client, "IT-000001", "A-01") == before_from - 30
    assert _location_on_hand(client, "IT-000001", "A-02") == before_to + 30


def test_move_to_same_location_is_rejected(client, seeded):
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("A-01")
    res = client.post(
        "/api/transfers/move",
        json={
            "batch_id": batch_id,
            "from_location_id": from_loc,
            "to_location_id": from_loc,
            "quantity": 5,
        },
    )
    assert res.status_code == 400
    assert "不可相同" in res.get_json()["error"]


def test_move_more_than_available_is_rejected(client, seeded):
    login(client, "warehouse")
    item_id, batch_id, from_loc, _ = _ids("A-01")
    available = _location_on_hand(client, "IT-000001", "A-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-02" and loc["warehouse_code"] == "WH-NH"
    )
    res = client.post(
        "/api/transfers/move",
        json={
            "batch_id": batch_id,
            "from_location_id": from_loc,
            "to_location_id": to_loc,
            "quantity": available + 1,
        },
    )
    assert res.status_code == 400
    assert "可用量" in res.get_json()["error"]


# --- AC-2 跨倉調貨出庫 ---
def test_transfer_ship_moves_stock_to_transit(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    item_id, batch_id, from_loc, _ = _ids("B-01")  # 中港倉 B-01

    before_in_transit = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["in_transit"]
    before_b01 = _location_on_hand(client, "IT-000001", "B-01")

    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "demand_source": "南港缺貨",
            "lines": [
                {"batch_id": batch_id, "from_location_id": from_loc, "quantity": 50}
            ],
        },
    )
    assert created.status_code == 201, created.get_json()
    order_id = created.get_json()["id"]
    assert created.get_json()["code"].startswith("TO-")

    shipped = client.post(f"/api/transfers/transfer-orders/{order_id}/ship")
    assert shipped.status_code == 200, shipped.get_json()
    assert shipped.get_json()["status"] == "in_transit"

    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["in_transit"] == before_in_transit + 50
    assert _location_on_hand(client, "IT-000001", "B-01") == before_b01 - 50
    assert row["balance_diff"] == 0.0


# --- AC-3 收貨 ---
def test_transfer_receive_moves_stock_to_destination(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-01" and loc["warehouse_code"] == "WH-NH"
    )

    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 50}],
        },
    )
    order_id = created.get_json()["id"]
    client.post(f"/api/transfers/transfer-orders/{order_id}/ship")

    before_in_transit = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["in_transit"]
    before_a01 = _location_on_hand(client, "IT-000001", "A-01")

    line_id = client.get("/api/transfers/transfer-orders").get_json()["data"][0]["lines"][0]["id"]
    received = client.post(
        f"/api/transfers/transfer-orders/{order_id}/receive",
        json={"receipts": [{"line_id": line_id, "quantity": 50, "location_id": to_loc}]},
    )
    assert received.status_code == 200, received.get_json()
    assert received.get_json()["status"] == "received"

    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["in_transit"] == before_in_transit - 50
    assert _location_on_hand(client, "IT-000001", "A-01") == before_a01 + 50
    assert row["balance_diff"] == 0.0


# --- AC-4 短缺 ---
def test_transfer_shortage_keeps_quantity_conserved(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-01" and loc["warehouse_code"] == "WH-NH"
    )

    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 50}],
        },
    )
    order_id = created.get_json()["id"]
    client.post(f"/api/transfers/transfer-orders/{order_id}/ship")
    line_id = client.get("/api/transfers/transfer-orders").get_json()["data"][0]["lines"][0]["id"]

    before_total = _on_hand(client)
    client.post(
        f"/api/transfers/transfer-orders/{order_id}/receive",
        json={"receipts": [{"line_id": line_id, "quantity": 45, "location_id": to_loc}]},
    )

    # 短缺 5 件留在在途位置 → 總量守恆
    assert _on_hand(client) == before_total
    order = client.get("/api/transfers/transfer-orders").get_json()["data"][0]
    line = order["lines"][0]
    assert line["received_quantity"] == 45.0
    assert line["shortage"] == 5.0


# --- AC-5 超量調出被拒 ---
def test_transfer_more_than_available_is_rejected(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    available = _location_on_hand(client, "IT-000001", "B-01")
    res = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [
                {"batch_id": batch_id, "from_location_id": from_loc, "quantity": available + 1}
            ],
        },
    )
    assert res.status_code == 400
    assert "可用量" in res.get_json()["error"]


# --- AC-6 狀態機保護 ---
def test_cannot_receive_before_ship(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-01" and loc["warehouse_code"] == "WH-NH"
    )
    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 10}],
        },
    )
    order_id = created.get_json()["id"]
    line_id = client.get("/api/transfers/transfer-orders").get_json()["data"][0]["lines"][0]["id"]

    res = client.post(
        f"/api/transfers/transfer-orders/{order_id}/receive",
        json={"receipts": [{"line_id": line_id, "quantity": 10, "location_id": to_loc}]},
    )
    assert res.status_code == 400
    assert "不可收貨" in res.get_json()["error"]


def test_cannot_ship_twice(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 10}],
        },
    )
    order_id = created.get_json()["id"]
    assert client.post(f"/api/transfers/transfer-orders/{order_id}/ship").status_code == 200
    res = client.post(f"/api/transfers/transfer-orders/{order_id}/ship")
    assert res.status_code == 400
    assert "不可出庫" in res.get_json()["error"]


# --- AC-7 稽核 ---
def test_transfer_writes_audit(client, seeded, warehouses, app):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    locations = client.get("/api/locations").get_json()["data"]
    to_loc = next(
        loc["id"] for loc in locations if loc["code"] == "A-01" and loc["warehouse_code"] == "WH-NH"
    )
    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 10}],
        },
    )
    order_id = created.get_json()["id"]
    client.post(f"/api/transfers/transfer-orders/{order_id}/ship")
    line_id = client.get("/api/transfers/transfer-orders").get_json()["data"][0]["lines"][0]["id"]
    client.post(
        f"/api/transfers/transfer-orders/{order_id}/receive",
        json={"receipts": [{"line_id": line_id, "quantity": 10, "location_id": to_loc}]},
    )

    with app.app_context():
        actions = {a.action for a in db.session.query(AuditLog).all()}
    assert "TRANSFER_CREATED" in actions
    assert "TRANSFER_SHIPPED" in actions
    assert "TRANSFER_RECEIVED" in actions


# --- AC-8 權限 ---
def test_sales_cannot_create_transfer(client, seeded, warehouses):
    login(client, "sales")
    res = client.post(
        "/api/transfers/transfer-orders",
        json={"from_warehouse_id": 1, "to_warehouse_id": 2, "lines": []},
    )
    assert res.status_code == 403


def test_same_warehouse_transfer_is_rejected(client, seeded, warehouses):
    nh_id, _ = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("A-01")
    res = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": nh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 1}],
        },
    )
    assert res.status_code == 400
    assert "不可相同" in res.get_json()["error"]


# --- AC-9 一致性：在手量 = 實體倉合計 + 在途量 ---
def test_on_hand_equals_real_plus_transit(client, seeded, warehouses):
    nh_id, kh_id = warehouses
    login(client, "warehouse")
    _, batch_id, from_loc, _ = _ids("B-01")
    created = client.post(
        "/api/transfers/transfer-orders",
        json={
            "from_warehouse_id": kh_id,
            "to_warehouse_id": nh_id,
            "lines": [{"batch_id": batch_id, "from_location_id": from_loc, "quantity": 20}],
        },
    )
    order_id = created.get_json()["id"]
    client.post(f"/api/transfers/transfer-orders/{order_id}/ship")

    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["on_hand"] == row["real_on_hand"] + row["in_transit"]
    assert row["balance_diff"] == 0.0
    # 在途不計入可用量
    assert row["available"] == row["real_on_hand"] - row["allocated"]
