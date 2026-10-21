"""切片 1 驗收測試（對應 spec 的 AC-1 ~ AC-9）。"""

from __future__ import annotations

from app.extensions import db
from app.models import AuditLog, User
from conftest import login


# --- AC-1 登入成功 ---
def test_login_success_returns_user(client, seeded):
    res = login(client)
    assert res.status_code == 200
    body = res.get_json()
    assert body["user"]["username"] == "warehouse"
    assert body["user"]["role"] == "warehouse"


def test_login_with_wrong_password_returns_401_generic_message(client, seeded):
    res = client.post("/api/auth/login", json={"username": "warehouse", "password": "wrong"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "帳號或密碼錯誤"


def test_login_with_unknown_user_returns_same_generic_message(client, seeded):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "帳號或密碼錯誤"


# --- AC-2 連續失敗鎖定 ---
def test_five_failures_lock_the_account(client, seeded):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    res = client.post("/api/auth/login", json={"username": "warehouse", "password": "Test@1234"})
    assert res.status_code == 423
    assert "鎖定" in res.get_json()["error"]


def test_lock_event_written_to_audit_log(client, seeded, app):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    with app.app_context():
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "LOGIN_FAILED" in actions


# --- AC-3 未登入不可存取 ---
def test_protected_endpoint_requires_login(client, seeded):
    res = client.get("/api/stock/query")
    assert res.status_code == 401


# --- AC-4 伺服器端角色控管 ---
def test_sales_role_cannot_create_item(client, seeded):
    login(client, "sales")
    res = client.post("/api/items", json={"name": "測試商品"})
    assert res.status_code == 403


def test_admin_can_create_item_and_code_is_generated(client, seeded):
    login(client, "admin")
    res = client.post("/api/items", json={"name": "測試商品", "unit": "個"})
    assert res.status_code == 201
    assert res.get_json()["code"] == "IT-000006"


def test_warehouse_role_can_query_stock(client, seeded):
    login(client, "warehouse")
    res = client.get("/api/stock/query")
    assert res.status_code == 200
    assert res.get_json()["total"] > 0


def test_purchasing_role_cannot_see_customer_names(client, seeded):
    login(client, "purchasing")
    res = client.get("/api/customers")
    assert res.status_code == 200
    names = [c["name"] for c in res.get_json()["data"]]
    assert all("不可見" in n for n in names)


# --- AC-5 庫存查詢數字一致 ---
def test_stock_numbers_match_seed_data(client, seeded):
    login(client, "warehouse")
    rows = client.get("/api/stock/query?q=IT-000001").get_json()["data"]
    assert len(rows) == 1
    row = rows[0]
    # 種子：南港 A-01 120、南港 A-02 30、中港 B-01 185（200 移出 15）、在途 15
    assert row["on_hand"] == 350.0
    assert row["in_transit"] == 15.0
    assert row["real_on_hand"] == 335.0
    assert row["available"] == 350.0  # 尚無配置量


def test_available_equals_on_hand_minus_allocations(client, seeded, app):
    """可用量必須由在手量扣除配置量算出，不可硬編碼。"""
    from app.models import Allocation, Batch, Item, Location, StockBalance

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000001").first()
        batch = db.session.query(Batch).filter_by(code="B20260415-001").first()
        loc = (
            db.session.query(Location)
            .filter_by(code="A-01")
            .join(Location.warehouse)
            .first()
        )
        db.session.add(
            Allocation(
                doc_type="SO",
                doc_id=1,
                item_id=item.id,
                batch_id=batch.id,
                location_id=loc.id,
                qty=20,
                status="active",
            )
        )
        db.session.commit()

    client2 = client
    login(client2, "warehouse")
    row = client2.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["on_hand"] == 350.0
    assert row["available"] == 330.0


# --- AC-6 快速定位 ---
def test_partial_name_search_matches(client, seeded):
    login(client, "warehouse")
    rows = client.get("/api/stock/query?q=螺絲").get_json()["data"]
    assert len(rows) == 1
    assert "螺絲" in rows[0]["name"]


def test_results_sorted_by_available_desc(client, seeded):
    login(client, "warehouse")
    rows = client.get("/api/stock/query").get_json()["data"]
    values = [r["available"] for r in rows]
    assert values == sorted(values, reverse=True)


# --- AC-7 稽核紀錄 ---
def test_successful_login_writes_audit_log(client, seeded, app):
    login(client)
    with app.app_context():
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "LOGIN_SUCCESS" in actions


def test_audit_log_has_no_delete_endpoint(client, seeded):
    login(client, "admin")
    assert client.delete("/api/audit-logs").status_code == 404


# --- AC-8 種子資料可重建（冪等）---
def test_seed_is_idempotent(app, seeded):
    from app.seed import _seed
    from app.models import Item, StockLedger

    with app.app_context():
        _seed(app.config["SEED_PASSWORD"])
        items = db.session.query(Item).count()
        ledger = db.session.query(StockLedger).count()
    assert items == 5
    assert ledger == 11  # 9 筆初始入庫 + 2 筆調貨移出／在途


def test_seed_creates_five_role_accounts(app, seeded):
    with app.app_context():
        roles = {u.role for u in db.session.query(User).all()}
    assert roles == {"admin", "warehouse", "purchasing", "sales", "accounting"}


# --- AC-9 前端流程（以 API 行為驗證）---
def test_logout_clears_session(client, seeded):
    login(client)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
