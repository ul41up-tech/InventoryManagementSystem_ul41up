"""切片 2 驗收測試：入庫、批次建立與庫存異動帳寫入。

對應 spec：`_bmad-output/implementation-artifacts/spec-mvp-slice-2-入庫與批次建立.md`
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db
from app.models import AuditLog, Batch, Grn, GrnLine, Item, Location, StockLedger, Warehouse
from conftest import login


@pytest.fixture()
def po(client, seeded):
    """建立一張草稿採購單：IT-000001 × 100，預估單價 45。"""
    login(client, "purchasing")
    res = client.post(
        "/api/purchase-orders",
        json={
            "supplier_id": 1,
            "lines": [{"item_id": 1, "quantity": 100, "unit_price": 45}],
        },
    )
    assert res.status_code == 201, res.get_json()
    data = res.get_json()
    client.post("/api/auth/logout")
    return data


def _location_id(code: str = "A-01") -> int:
    loc = db.session.query(Location).filter_by(code=code).join(Location.warehouse).first()
    return loc.id


def _item_id(code: str = "IT-000001") -> int:
    return db.session.query(Item).filter_by(code=code).first().id


# --- AC-1 對採購單入庫 ---
def test_receive_against_purchase_order(client, seeded, po, app):
    login(client, "warehouse")
    po_lines = client.get("/api/purchase-orders").get_json()["data"]
    po_id = po_lines[0]["id"]
    po_line_id = po_lines[0]["lines"][0]["id"]

    before = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["on_hand"]

    res = client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_id,
            "lines": [
                {
                    "item_id": po_lines[0]["lines"][0]["item_id"],
                    "purchase_order_line_id": po_line_id,
                    "quantity": 95,
                    "unit_cost": 46,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["code"].startswith("GR-")
    assert len(body["batch_codes"]) == 1
    assert body["batch_codes"][0].startswith("B")

    after = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert after["on_hand"] == before + 95

    # 待入庫數量由 100 變成 5
    po_after = client.get("/api/purchase-orders").get_json()["data"][0]
    line = po_after["lines"][0]
    assert line["received_quantity"] == 95.0
    assert line["pending_quantity"] == 5.0


def test_receive_twice_accumulates(client, seeded, po):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]

    for qty in (60, 40):
        res = client.post(
            "/api/grn",
            json={
                "purchase_order_id": po_data["id"],
                "lines": [
                    {
                        "item_id": po_line["item_id"],
                        "purchase_order_line_id": po_line["id"],
                        "quantity": qty,
                        "unit_cost": 45,
                        "location_id": _location_id("A-01"),
                    }
                ],
            },
        )
        assert res.status_code == 201, res.get_json()

    po_after = client.get("/api/purchase-orders").get_json()["data"][0]["lines"][0]
    assert po_after["received_quantity"] == 100.0
    assert po_after["pending_quantity"] == 0.0


# --- AC-2 超過待入庫數量被拒 ---
def test_receive_more_than_pending_is_rejected(client, seeded, po):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    before = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["on_hand"]

    res = client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 101,
                    "unit_cost": 45,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )
    assert res.status_code == 400
    assert "待入庫" in res.get_json()["error"]

    after = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert after["on_hand"] == before  # 庫存不受影響


# --- AC-3 批次建立 ---
def test_batch_created_with_actual_unit_cost(client, seeded, po, app):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 10,
                    "unit_cost": 47,  # 與採購預估價 45 不同 → 以實際價為準
                    "location_id": _location_id("A-02"),
                }
            ],
        },
    )
    with app.app_context():
        batch = db.session.query(Batch).order_by(Batch.id.desc()).first()
        assert batch.code.startswith("B")
        assert batch.actual_unit_cost == Decimal("47")
        assert batch.quantity == Decimal("10")
        assert batch.purchase_order_id == po_data["id"]
        assert batch.in_date is not None


# --- AC-4 異動帳與餘額一致 ---
def test_ledger_and_balance_stay_consistent(client, seeded, po):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 30,
                    "unit_cost": 45,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )
    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["balance_diff"] == 0.0  # ledger 與快取無差額


def test_ledger_row_written_for_receiving(client, seeded, po, app):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    before = db.session.query(StockLedger).count() if app else 0
    client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 7,
                    "unit_cost": 45,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )
    with app.app_context():
        after = db.session.query(StockLedger).count()
        rows = db.session.query(StockLedger).order_by(StockLedger.id.desc()).limit(1).all()
        assert after == before + 1
        assert rows[0].move_type == "GRN"
        assert rows[0].qty == Decimal("7")


# --- AC-5 稽核紀錄 ---
def test_receiving_writes_audit_log(client, seeded, po, app):
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 12,
                    "unit_cost": 45,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )
    with app.app_context():
        entries = db.session.query(AuditLog).filter_by(action="GRN_POSTED").all()
        assert entries, "應有 GRN_POSTED 稽核紀錄"
        entry = entries[-1]
        assert entry.operator_name == "warehouse"
        assert entry.qty == Decimal("12")
        assert entry.location_id is not None
        assert entry.batch_id is not None


# --- AC-6 手動入庫 ---
def test_manual_receiving_requires_admin(client, seeded):
    login(client, "warehouse")
    res = client.post(
        "/api/grn",
        json={
            "manual": True,
            "reason": "盤點剩餘",
            "lines": [
                {
                    "item_id": _item_id(),
                    "quantity": 5,
                    "unit_cost": 45,
                    "location_id": _location_id(),
                }
            ],
        },
    )
    assert res.status_code == 403


def test_manual_receiving_requires_reason(client, seeded):
    login(client, "admin")
    res = client.post(
        "/api/grn",
        json={
            "manual": True,
            "lines": [
                {
                    "item_id": _item_id(),
                    "quantity": 5,
                    "unit_cost": 45,
                    "location_id": _location_id(),
                }
            ],
        },
    )
    assert res.status_code == 400
    assert "原因" in res.get_json()["error"]


def test_manual_receiving_creates_batch(client, seeded):
    login(client, "admin")
    before = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["on_hand"]
    res = client.post(
        "/api/grn",
        json={
            "manual": True,
            "reason": "供應商gift補貨（測試）",
            "lines": [
                {
                    "item_id": _item_id(),
                    "quantity": 5,
                    "unit_cost": 45,
                    "location_id": _location_id(),
                }
            ],
        },
    )
    assert res.status_code == 201, res.get_json()
    after = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert after["on_hand"] == before + 5


# --- AC-7 位置入口入庫 ---
def test_location_items_endpoint(client, seeded):
    login(client, "warehouse")
    loc_id = _location_id("A-01")
    res = client.get(f"/api/grn/locations/{loc_id}/items")
    assert res.status_code == 200
    body = res.get_json()
    assert body["location"]["code"] == "A-01"
    assert any(i["item_code"] == "IT-000001" for i in body["items"])


def test_location_items_unknown_location_returns_404(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/grn/locations/999999/items").status_code == 404


def test_receive_by_location_entry(client, seeded, po):
    """以位置為入口入庫（FR-27）：倉管對採購單，指定位置輸入數量。"""
    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    loc_id = _location_id("A-02")
    before = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["on_hand"]

    res = client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 3,
                    "unit_cost": 45,
                    "location_id": loc_id,
                }
            ],
        },
    )
    assert res.status_code == 201, res.get_json()
    after = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]["on_hand"]
    assert after == before + 3


# --- AC-8 負庫存防護（服務層）---
def test_available_cannot_go_negative(app, seeded):
    """配置量超過在手量時，服務層必須拒絕任何異動。"""
    from app.models import Allocation
    from app.services.stock_service import StockError, assert_available_non_negative

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000001").first()
        batch = db.session.query(Batch).filter_by(item_id=item.id).first()
        db.session.add(
            Allocation(
                doc_type="SO",
                doc_id=1,
                item_id=item.id,
                batch_id=batch.id,
                location_id=_location_id(),
                qty=9999,
                status="active",
            )
        )
        db.session.commit()
        with pytest.raises(StockError):
            assert_available_non_negative(item.id)


# --- AC-9 權限 ---
def test_sales_cannot_create_grn(client, seeded):
    login(client, "sales")
    res = client.post(
        "/api/grn",
        json={
            "manual": True,
            "reason": "測試",
            "lines": [
                {
                    "item_id": _item_id(),
                    "quantity": 1,
                    "unit_cost": 45,
                    "location_id": _location_id(),
                }
            ],
        },
    )
    assert res.status_code == 403


def test_accounting_can_list_grn(client, seeded):
    login(client, "accounting")
    assert client.get("/api/grn").status_code == 200


def test_only_admin_can_create_warehouse_and_location(client, seeded):
    login(client, "warehouse")
    assert client.post("/api/warehouses", json={"code": "WH-X", "name": "測試倉"}).status_code == 403
    assert client.post("/api/locations", json={"code": "X-01", "name": "測試位", "warehouse_id": 1}).status_code == 403

    login(client, "admin")
    assert client.post("/api/warehouses", json={"code": "WH-X", "name": "測試倉"}).status_code == 201
    assert (
        client.post("/api/locations", json={"code": "X-01", "name": "測試位", "warehouse_id": 1}).status_code
        == 201
    )


# --- AC-10 種子冪等性不受入庫影響 ---
def test_seed_stays_idempotent_after_receiving(client, seeded, po, app):
    from app.seed import _seed

    login(client, "warehouse")
    po_data = client.get("/api/purchase-orders").get_json()["data"][0]
    po_line = po_data["lines"][0]
    client.post(
        "/api/grn",
        json={
            "purchase_order_id": po_data["id"],
            "lines": [
                {
                    "item_id": po_line["item_id"],
                    "purchase_order_line_id": po_line["id"],
                    "quantity": 5,
                    "unit_cost": 45,
                    "location_id": _location_id("A-01"),
                }
            ],
        },
    )

    with app.app_context():
        batches_before = db.session.query(Batch).count()
        _seed(app.config["SEED_PASSWORD"])
        assert db.session.query(Batch).count() == batches_before  # 種子不重複建立批次
        assert db.session.query(Grn).count() >= 1  # 入庫單不受影響
