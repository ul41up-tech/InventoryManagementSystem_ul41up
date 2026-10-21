"""切片 1 驗收測試（對應 spec 的 AC-1 ~ AC-9）。"""

from __future__ import annotations

import datetime as dt

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


def test_login_with_non_string_payload_does_not_500(client, seeded):
    res = client.post("/api/auth/login", json={"username": 123, "password": ["x"]})
    assert res.status_code == 401


def test_login_with_array_body_does_not_500(client, seeded):
    res = client.post("/api/auth/login", json=["warehouse", "x"])
    assert res.status_code == 400


# --- AC-2 連續失敗鎖定 ---
def test_five_failures_lock_the_account(client, seeded):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    res = client.post("/api/auth/login", json={"username": "warehouse", "password": "Test@1234"})
    assert res.status_code == 423
    assert "鎖定" in res.get_json()["error"]


def test_lock_event_written_to_audit_log(client, seeded, app):
    """第 5 次失敗當下就要寫入 ACCOUNT_LOCKED（不是等下一次嘗試）。"""
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    with app.app_context():
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "ACCOUNT_LOCKED" in actions
    assert "LOGIN_FAILED" in actions


def test_lock_expiry_resets_failed_counter_and_writes_unlock_audit(client, seeded, app):
    """鎖定期過後失敗次數歸零，且留下解鎖紀錄。"""
    with app.app_context():
        user = db.session.query(User).filter_by(username="warehouse").one()
        user.failed_attempts = 5
        user.locked_until = dt.datetime.utcnow() - dt.timedelta(minutes=1)
        db.session.commit()

    res = client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    assert res.status_code == 401
    with app.app_context():
        user = db.session.query(User).filter_by(username="warehouse").one()
        assert user.failed_attempts == 1
        assert user.locked_until is None
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "ACCOUNT_UNLOCKED" in actions


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


def test_warehouse_role_cannot_read_suppliers(client, seeded):
    """PRD §4.1 權限矩陣：供應商主檔對倉管為不可見。"""
    login(client, "warehouse")
    assert client.get("/api/suppliers").status_code == 403


def test_warehouse_role_cannot_read_customers(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/customers").status_code == 403


def test_accounting_role_can_read_warehouses(client, seeded):
    login(client, "accounting")
    assert client.get("/api/warehouses").status_code == 200


def test_purchasing_role_cannot_see_customer_identity(client, seeded):
    """採購只見彙總：名稱、聯絡人、電話都不得外洩。"""
    login(client, "purchasing")
    res = client.get("/api/customers")
    assert res.status_code == 200
    for row in res.get_json()["data"]:
        assert "不可見" in row["name"]
        assert row["contact"] is None
        assert row["phone"] is None


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
    assert row["balance_diff"] == 0.0  # ledger 與快取一致


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

    login(client, "warehouse")
    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]
    assert row["on_hand"] == 350.0
    assert row["available"] == 330.0


def test_unmatched_allocation_still_reduces_available(client, seeded, app):
    """沒有對應餘額列的配置也必須扣減可用量（否則可用量被高估）。"""
    from app.models import Allocation, Batch, Item

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000005").first()
        batch = db.session.query(Batch).filter_by(item_id=item.id).first()
        db.session.add(
            Allocation(
                doc_type="SO",
                doc_id=99,
                item_id=item.id,
                batch_id=batch.id,
                location_id=999999,  # 不存在的位置
                qty=5,
                status="active",
            )
        )
        db.session.commit()

    login(client, "warehouse")
    row = client.get("/api/stock/query?q=IT-000005").get_json()["data"][0]
    assert row["on_hand"] == 500.0
    assert row["available"] == 495.0


def test_location_breakdown_matches_allocation(client, seeded, app):
    """位置層的配置必須被歸屬到正確的位置（批次跨位置時也要正確）。"""
    from app.models import Allocation, Batch, Item, Location

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000001").first()
        # B20260415-003 跨兩個位置：中港 B-01 與 TRANSIT（在途）
        batch = db.session.query(Batch).filter_by(code="B20260415-003").first()
        loc_b01 = (
            db.session.query(Location).filter_by(code="B-01").join(Location.warehouse).first()
        )
        db.session.add(
            Allocation(
                doc_type="SO",
                doc_id=2,
                item_id=item.id,
                batch_id=batch.id,
                location_id=loc_b01.id,
                qty=30,
                status="active",
            )
        )
        db.session.commit()

    login(client, "warehouse")
    row = client.get("/api/stock/query?q=IT-000001").get_json()["data"][0]

    by_loc = {}
    for loc in row["locations"]:
        by_loc[(loc["location_code"], loc["batch_code"])] = loc

    b01 = by_loc[("B-01", "B20260415-003")]
    assert b01["on_hand"] == 185.0
    assert b01["allocated"] == 30.0
    assert b01["available"] == 155.0

    # 在途位置不應承擔配置
    transit = by_loc[("TRANSIT", "B20260415-003")]
    assert transit["allocated"] == 0.0
    assert transit["on_hand"] == 15.0

    assert row["available"] == 350.0 - 30.0


def test_stock_numbers_come_from_ledger_not_cache(client, seeded, app):
    """在手量以 ledger 為準；快取與 ledger 不一致時回報 diff。"""
    from app.models import Item, StockBalance

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000002").first()
        balance = db.session.query(StockBalance).filter_by(item_id=item.id).first()
        balance.qty = 999  # 快取被改壞
        db.session.commit()

    login(client, "warehouse")
    row = client.get("/api/stock/query?q=IT-000002").get_json()["data"][0]
    assert row["on_hand"] == 230.0  # ledger：80 + 150
    assert row["balance_diff"] != 0.0


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


def test_invalid_limit_does_not_500(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/stock/query?limit=abc").status_code == 200
    assert client.get("/api/stock/query?limit=-5").status_code == 200
    assert client.get("/api/stock/query?limit=0").status_code == 200


def test_total_reflects_matches_not_page_size(client, seeded):
    login(client, "warehouse")
    body = client.get("/api/stock/query?limit=1").get_json()
    assert body["total"] == 5  # 符合條件的總數
    assert len(body["data"]) == 1


# --- AC-7 稽核紀錄 ---
def test_successful_login_writes_audit_log(client, seeded, app):
    login(client)
    with app.app_context():
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "LOGIN_SUCCESS" in actions


def test_audit_log_has_no_delete_endpoint(client, seeded):
    """操作紀錄不可刪除：DELETE／PUT 方法不被接受。"""
    login(client, "admin")
    assert client.delete("/api/audit-logs").status_code in (404, 405)
    assert client.put("/api/audit-logs", json={}).status_code in (404, 405)


def test_logout_and_item_creation_and_access_denied_are_audited(client, seeded, app):
    """AC-7 指定的稽核事件都要真的寫進去。"""
    login(client, "admin")
    client.post("/api/items", json={"name": "稽核測試商品"})
    client.post("/api/auth/logout")

    login(client, "sales")
    client.post("/api/items", json={"name": "越權測試商品"})

    with app.app_context():
        actions = [a.action for a in db.session.query(AuditLog).all()]
    assert "ITEM_CREATED" in actions
    assert "LOGOUT" in actions
    assert "ACCESS_DENIED" in actions


def test_audit_logs_are_readable_by_admin_and_accounting(client, seeded):
    login(client, "admin")
    res = client.get("/api/audit-logs")
    assert res.status_code == 200
    assert res.get_json()["total"] > 0


def test_audit_logs_not_readable_by_warehouse(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/audit-logs").status_code == 403


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


def test_seed_does_not_overwrite_existing_role(app, seeded):
    """管理者在系統內調整的角色不應被重跑種子覆蓋。"""
    from app.seed import _seed

    with app.app_context():
        user = db.session.query(User).filter_by(username="sales").one()
        user.role = "admin"
        db.session.commit()
        _seed(app.config["SEED_PASSWORD"])
        user = db.session.query(User).filter_by(username="sales").one()
        assert user.role == "admin"


# --- AC-9 前端流程（以 API 行為驗證）---
def test_logout_clears_session(client, seeded):
    login(client)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_change_password_flow(client, seeded):
    """首次登入後強制改密：舊密碼錯誤被拒，改後可用新密碼登入。"""
    login(client, "warehouse")
    bad = client.post(
        "/api/auth/change-password",
        json={"old_password": "wrong", "new_password": "NewPass@123"},
    )
    assert bad.status_code == 400

    too_short = client.post(
        "/api/auth/change-password",
        json={"old_password": "Test@1234", "new_password": "abc"},
    )
    assert too_short.status_code == 400

    ok = client.post(
        "/api/auth/change-password",
        json={"old_password": "Test@1234", "new_password": "NewPass@123"},
    )
    assert ok.status_code == 200

    client.post("/api/auth/logout")
    again = client.post(
        "/api/auth/login", json={"username": "warehouse", "password": "NewPass@123"}
    )
    assert again.status_code == 200
    assert again.get_json()["user"]["must_change_password"] is False

# --- PRD §4.1 權限矩陣：主檔讀取逐格驗證（SM-7）---
import pytest  # noqa: E402

MATRIX_READ = {
    "/api/items": {"admin": 200, "warehouse": 200, "purchasing": 200, "sales": 200, "accounting": 200},
    "/api/suppliers": {"admin": 200, "warehouse": 403, "purchasing": 200, "sales": 200, "accounting": 200},
    "/api/customers": {"admin": 200, "warehouse": 403, "purchasing": 200, "sales": 200, "accounting": 200},
    # 倉庫／位置：全部角色可檢視（入庫需選位置），但僅管理員可維護（見 slice 2 修訂）
    "/api/warehouses": {"admin": 200, "warehouse": 200, "purchasing": 200, "sales": 200, "accounting": 200},
    "/api/locations": {"admin": 200, "warehouse": 200, "purchasing": 200, "sales": 200, "accounting": 200},
}


@pytest.mark.parametrize("path", sorted(MATRIX_READ))
def test_master_data_read_matrix(path, client, seeded):
    for role, expected in MATRIX_READ[path].items():
        client.post("/api/auth/logout")
        login(client, role)
        res = client.get(path)
        assert res.status_code == expected, f"{role} 讀取 {path} 預期 {expected}，實際 {res.status_code}"


# --- 批次明細端點 ---
def test_item_batches_returns_only_that_item(client, seeded, app):
    from app.models import Item

    with app.app_context():
        item = db.session.query(Item).filter_by(code="IT-000001").one()
        item_id = item.id

    login(client, "warehouse")
    res = client.get(f"/api/stock/items/{item_id}/batches")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data, "應至少有一筆批次"
    assert all(row["batch_code"].startswith("B20260415-") for row in data)
    # 成本與位置都要有值
    assert all(row["actual_unit_cost"] > 0 for row in data)
    assert all(row["location_code"] for row in data)


def test_item_batches_unknown_item_returns_404(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/stock/items/999999/batches").status_code == 404


# --- migration 產物涵蓋全部資料表 ---
def test_initial_migration_covers_all_tables():
    """產出的初始 migration 必須涵蓋 models 定義的所有資料表。"""
    import os
    import re

    from app.extensions import db as _db
    from app import models  # noqa: F401

    migration = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "versions",
        "0001_initial_schema.py",
    )
    assert os.path.exists(migration), "尚未產生初始 migration，請執行 tools/generate_initial_migration.py"
    content = open(migration, encoding="utf-8").read()
    created = set(re.findall(r"CREATE TABLE (\w+)", content))
    expected = set(_db.metadata.tables.keys())
    assert expected <= created, f"migration 缺少資料表：{sorted(expected - created)}"

# --- FR-26 帳號與角色管理（僅管理員）---
def test_admin_can_create_and_deactivate_user(client, seeded):
    login(client, "admin")
    created = client.post(
        "/api/users",
        json={"username": "newhire", "name": "新進人員", "role": "warehouse", "password": "NewHire@2026"},
    )
    assert created.status_code == 201
    user_id = created.get_json()["id"]

    listed = client.get("/api/users").get_json()["data"]
    assert any(u["username"] == "newhire" for u in listed)

    disabled = client.patch(f"/api/users/{user_id}", json={"is_active": False})
    assert disabled.status_code == 200

    # 停用後不得登入
    other = client.application.test_client()
    res = other.post("/api/auth/login", json={"username": "newhire", "password": "NewHire@2026"})
    assert res.status_code == 403


def test_duplicate_username_returns_409(client, seeded):
    login(client, "admin")
    res = client.post(
        "/api/users",
        json={"username": "admin", "name": "重複", "role": "sales", "password": "NewHire@2026"},
    )
    assert res.status_code == 409


def test_non_admin_cannot_manage_users(client, seeded):
    login(client, "warehouse")
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users", json={"username": "x", "name": "y", "role": "sales", "password": "Passw0rd!"}).status_code == 403


def test_admin_cannot_deactivate_self(client, seeded):
    login(client, "admin")
    me = client.get("/api/auth/me").get_json()
    res = client.patch(f"/api/users/{me['id']}", json={"is_active": False})
    assert res.status_code == 409


def test_invalid_role_rejected(client, seeded):
    login(client, "admin")
    res = client.post(
        "/api/users", json={"username": "badrole", "name": "錯誤角色", "role": "hacker", "password": "Passw0rd!"}
    )
    assert res.status_code == 400


def test_admin_can_unlock_user(client, seeded, app):
    login(client, "admin")
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "warehouse", "password": "bad"})
    user_id = client.get("/api/users").get_json()["data"]
    target = [u for u in user_id if u["username"] == "warehouse"][0]
    assert target["locked"] is True
    assert client.post(f"/api/users/{target['id']}/unlock").status_code == 200
