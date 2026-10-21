"""種子資料（flask seed）。

建立可登入的五種角色帳號、示範倉庫／位置、供應商、客戶、商品、批次，
以及對應的庫存異動帳與餘額（PRD §6.1 種子資料為交付物；AC-8 要求冪等）。

預設密碼由環境變數 SEED_PASSWORD 提供，**不得硬編碼於版本控制**。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import (
    ROLE_ADMIN,
    ROLE_ACCOUNTING,
    ROLE_PURCHASING,
    ROLE_SALES,
    ROLE_WAREHOUSE,
    Allocation,
    Batch,
    Customer,
    Item,
    ItemSupplier,
    Location,
    StockBalance,
    StockLedger,
    Supplier,
    User,
    Warehouse,
)
from .security import hash_password, write_audit

SEED_USERS = [
    ("admin", "系統管理員", ROLE_ADMIN),
    ("warehouse", "倉管阿哲", ROLE_WAREHOUSE),
    ("purchasing", "採購大明", ROLE_PURCHASING),
    ("sales", "業務小美", ROLE_SALES),
    ("accounting", "會計小陳", ROLE_ACCOUNTING),
]

SEED_SUPPLIERS = [
    ("12345678", "宏達五金股份有限公司", "王大明", "02-2345-6789"),
    ("87654321", "信譽塑膠工業有限公司", "李淑芬", "02-8765-4321"),
]

SEED_CUSTOMERS = [
    ("台北興業股份有限公司", "張經理", "0912-345-678"),
    ("高雄長榮貿易有限公司", "陳課長", "0922-345-678"),
]

SEED_ITEMS = [
    # code, name, unit, 建議售價, 預估毛利率, 供應商 index, 主供應商
    ("IT-000001", "M8 螺絲 盒裝 100 支", "盒", 120, 0.25, 0, True),
    ("IT-000002", "M8 螺帽 盒裝 100 個", "盒", 90, 0.25, 0, True),
    ("IT-000003", "PVC 電線 2.5mm 100 米", "卷", 1500, 0.20, 0, True),
    ("IT-000004", "ABS 外殼 藍色", "個", 350, 0.30, 1, True),
    ("IT-000005", "矽膠按键 紅色", "個", 28, 0.40, 1, True),
]


def register_seed_command(app):
    @app.cli.command("seed")
    @click.option("--password", default=None, help="種子帳號密碼；預設取環境變數 SEED_PASSWORD。")
    @with_appcontext
    def seed(password: str | None):
        """建立或更新種子資料（冪等）。"""
        pwd = password or app.config["SEED_PASSWORD"]
        created = _seed(pwd)
        click.echo(f"種子資料完成：{created}")

    return app


def _seed(password: str) -> str:
    summary = []

    # --- 使用者 ---
    for username, name, role in SEED_USERS:
        user = db.session.query(User).filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                name=name,
                role=role,
                password_hash=hash_password(password),
                must_change_password=True,
            )
            db.session.add(user)
            summary.append(f"建立帳號 {username}")
        else:
            user.role = role
            user.name = name
    db.session.flush()

    admin = db.session.query(User).filter_by(username="admin").first()

    # --- 倉庫（含虛擬在途位置）---
    warehouse_specs = [
        ("WH-NH", "南港倉", False),
        ("WH-KH", "中港倉", False),
        ("TRANSIT", "在途（虛擬）", True),
    ]
    warehouses: dict[str, Warehouse] = {}
    for code, name, virtual in warehouse_specs:
        wh = db.session.query(Warehouse).filter_by(code=code).first()
        if wh is None:
            wh = Warehouse(code=code, name=name, is_virtual=virtual)
            db.session.add(wh)
            db.session.flush()
            summary.append(f"建立倉庫 {code}")
        warehouses[code] = wh

    # --- 庫存位置 ---
    location_specs = [
        ("A-01", "南港倉 A 區 01 號架", "WH-NH"),
        ("A-02", "南港倉 A 區 02 號架", "WH-NH"),
        ("B-01", "中港倉 B 區 01 號架", "WH-KH"),
        ("TRANSIT", "在途（虛擬位置）", "TRANSIT"),
    ]
    locations: dict[str, Location] = {}
    for code, name, wh_code in location_specs:
        loc = (
            db.session.query(Location)
            .filter_by(code=code, warehouse_id=warehouses[wh_code].id)
            .first()
        )
        if loc is None:
            loc = Location(code=code, name=name, warehouse_id=warehouses[wh_code].id)
            db.session.add(loc)
            db.session.flush()
            summary.append(f"建立庫存位置 {wh_code}/{code}")
        locations[f"{wh_code}/{code}"] = loc

    # --- 供應商 ---
    suppliers: list[Supplier] = []
    for tax_id, name, contact, phone in SEED_SUPPLIERS:
        sup = db.session.query(Supplier).filter_by(tax_id=tax_id).first()
        if sup is None:
            sup = Supplier(tax_id=tax_id, name=name, contact=contact, phone=phone)
            db.session.add(sup)
            db.session.flush()
            summary.append(f"建立供應商 {name}")
        suppliers.append(sup)

    # --- 客戶 ---
    for name, contact, phone in SEED_CUSTOMERS:
        if db.session.query(Customer).filter_by(name=name).first() is None:
            db.session.add(Customer(name=name, contact=contact, phone=phone))
            summary.append(f"建立客戶 {name}")
    db.session.flush()

    # --- 商品 ---
    items: list[Item] = []
    for idx, (code, name, unit, price, margin, sup_idx, primary) in enumerate(SEED_ITEMS, start=1):
        item = db.session.query(Item).filter_by(code=code).first()
        if item is None:
            item = Item(
                code=code,
                name=name,
                unit=unit,
                suggested_price=Decimal(str(price)),
                target_margin_rate=Decimal(str(margin)),
            )
            db.session.add(item)
            db.session.flush()
            summary.append(f"建立商品 {code} {name}")
        items.append(item)
        link = (
            db.session.query(ItemSupplier)
            .filter_by(item_id=item.id, supplier_id=suppliers[sup_idx].id)
            .first()
        )
        if link is None:
            db.session.add(
                ItemSupplier(item_id=item.id, supplier_id=suppliers[sup_idx].id, is_primary=primary)
            )
    db.session.flush()

    # --- 批次與庫存異動（僅在尚無任何 ledger 紀錄時建立，避免重複）---
    if db.session.query(StockLedger).count() == 0:
        operator = db.session.query(User).filter_by(username="warehouse").first()
        in_date = dt.date(2026, 4, 15)
        transit_source = None

        # (item index, 倉庫, 位置, 數量, 實際單價)
        stock_specs = [
            (0, "WH-NH", "A-01", Decimal("120"), Decimal("45")),
            (0, "WH-NH", "A-02", Decimal("30"), Decimal("45")),
            (0, "WH-KH", "B-01", Decimal("200"), Decimal("46")),
            (1, "WH-NH", "A-01", Decimal("80"), Decimal("32")),
            (1, "WH-KH", "B-01", Decimal("150"), Decimal("33")),
            (2, "WH-NH", "A-02", Decimal("25"), Decimal("1150")),
            (3, "WH-NH", "A-01", Decimal("60"), Decimal("245")),
            (3, "WH-KH", "B-01", Decimal("40"), Decimal("250")),
            (4, "WH-NH", "A-02", Decimal("500"), Decimal("16")),
        ]
        for item_idx, wh_code, loc_code, qty, unit_cost in stock_specs:
            item = items[item_idx]
            seq = len([b for b in db.session.query(Batch).all()]) + 1
            batch_code = f"B{in_date.strftime('%Y%m%d')}-{seq:03d}"
            batch = Batch(
                code=batch_code,
                item_id=item.id,
                supplier_id=suppliers[0].id,
                actual_unit_cost=unit_cost,
                quantity=qty,
                in_date=in_date,
            )
            db.session.add(batch)
            db.session.flush()

            location = locations[f"{wh_code}/{loc_code}"]
            db.session.add(
                StockLedger(
                    item_id=item.id,
                    batch_id=batch.id,
                    location_id=location.id,
                    qty=qty,
                    move_type="GRN",
                    source_type="SEED",
                    source_id=batch.id,
                    operator_id=operator.id if operator else None,
                    note="種子資料：初始入庫",
                )
            )
            db.session.add(
                StockBalance(
                    item_id=item.id, batch_id=batch.id, location_id=location.id, qty=qty
                )
            )
            summary.append(f"建立批次 {batch_code} × {qty}")
            if item_idx == 0 and wh_code == "WH-KH":
                transit_source = (batch, location, qty)

        # 一筆在途數量示範：IT-000001 由中港倉調往南港倉（尚未收貨）
        # 同一批次：來源倉餘額減少、在途位置增加，批次剩餘量不變
        if transit_source is not None:
            batch, source_location, qty = transit_source
            transit_qty = Decimal("15")
            source_balance = (
                db.session.query(StockBalance)
                .filter_by(item_id=items[0].id, batch_id=batch.id, location_id=source_location.id)
                .one()
            )
            source_balance.qty = source_balance.qty - transit_qty
            db.session.add(
                StockLedger(
                    item_id=items[0].id,
                    batch_id=batch.id,
                    location_id=source_location.id,
                    qty=-transit_qty,
                    move_type="TRANSFER_OUT",
                    source_type="SEED",
                    source_id=batch.id,
                    operator_id=operator.id if operator else None,
                    note="種子資料：跨倉調貨移出",
                )
            )
            transit = locations["TRANSIT/TRANSIT"]
            db.session.add(
                StockLedger(
                    item_id=items[0].id,
                    batch_id=batch.id,
                    location_id=transit.id,
                    qty=transit_qty,
                    move_type="TRANSFER_OUT",
                    source_type="SEED",
                    source_id=batch.id,
                    operator_id=operator.id if operator else None,
                    note="種子資料：跨倉調貨在途",
                )
            )
            db.session.add(
                StockBalance(
                    item_id=items[0].id, batch_id=batch.id, location_id=transit.id, qty=transit_qty
                )
            )
            summary.append("建立在途數量示範 15 件")

    write_audit("SEED_EXECUTED", operator=admin, detail="種子資料建立／更新")
    db.session.commit()
    return "；".join(summary) if summary else "資料已存在，無變更"
