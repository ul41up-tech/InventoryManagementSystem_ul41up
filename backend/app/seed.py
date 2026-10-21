"""種子資料（flask seed）。

建立可登入的五種角色帳號、示範倉庫／位置、供應商、客戶、商品、批次，
以及對應的庫存異動帳與餘額（PRD §6.1 種子資料為交付物；AC-8 要求冪等）。

原則：
- **冪等且可重複執行**：以「物件是否已存在」判斷，而非以整張表是否為空判斷。
- **不覆蓋既有帳號的角色與姓名**（那是管理者在系統內的調整）。
- 僅在帳號**尚未自行改過密碼**（must_change_password 仍為 True）時套用新密碼。
- 密碼由環境變數 SEED_PASSWORD 或互動提示提供，不在原始碼內留預設值。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import (
    MOVE_GRN,
    MOVE_TRANSFER_OUT,
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

# (item index, 倉庫, 位置, 數量, 實際單價, 批次序號)
# 批次序號固定不變，讓重跑種子時能辨識同一批資料（冪等）。
SEED_STOCK = [
    (0, "WH-NH", "A-01", Decimal("120"), Decimal("45"), 1),
    (0, "WH-NH", "A-02", Decimal("30"), Decimal("45"), 2),
    (0, "WH-KH", "B-01", Decimal("200"), Decimal("46"), 3),
    (1, "WH-NH", "A-01", Decimal("80"), Decimal("32"), 4),
    (1, "WH-KH", "B-01", Decimal("150"), Decimal("33"), 5),
    (2, "WH-NH", "A-02", Decimal("25"), Decimal("1150"), 6),
    (3, "WH-NH", "A-01", Decimal("60"), Decimal("245"), 7),
    (3, "WH-KH", "B-01", Decimal("40"), Decimal("250"), 8),
    (4, "WH-NH", "A-02", Decimal("500"), Decimal("16"), 9),
]

SEED_IN_DATE = dt.date(2026, 4, 15)
SEED_TRANSIT_QTY = Decimal("15")


def register_seed_command(app):
    @app.cli.command("seed")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=False,
        default=None,
        help="種子帳號初始密碼；留空則取環境變數 SEED_PASSWORD。",
    )
    @with_appcontext
    def seed(password: str | None):
        """建立或更新種子資料（冪等）。"""
        pwd = password or app.config.get("SEED_PASSWORD") or ""
        if not pwd:
            raise click.ClickException(
                "未提供密碼：請設定環境變數 SEED_PASSWORD，或在提示時輸入。"
                "（不接受預設值，避免所有種子帳號共用公開密碼）"
            )
        summary = _seed(pwd)
        click.echo("種子資料完成：")
        for line in summary:
            click.echo(f"  - {line}")
        click.echo("")
        click.echo("提醒：所有種子帳號標記為「首次登入須修改密碼」，請於首次登入後立即更改。")

    return app


def _seed(password: str) -> list[str]:
    summary: list[str] = []

    # --- 使用者（不覆蓋既有帳號的角色與姓名）---
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
            summary.append(f"建立帳號 {username}（{role}）")
        elif user.must_change_password:
            # 尚未自行改過密碼 → 套用本次的初始密碼
            user.password_hash = hash_password(password)
            user.must_change_password = True
            summary.append(f"重設帳號 {username} 的初始密碼")
        else:
            summary.append(f"帳號 {username} 已存在且已改過密碼，略過")

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
    for code, name, unit, price, margin, sup_idx, primary in SEED_ITEMS:
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

    # --- 批次與庫存異動（以批次是否存在判斷，可重複執行）---
    operator = db.session.query(User).filter_by(username="warehouse").first()
    transit_source: tuple[Batch, Location, Decimal] | None = None

    for item_idx, wh_code, loc_code, qty, unit_cost, batch_seq in SEED_STOCK:
        item = items[item_idx]
        batch_code = f"B{SEED_IN_DATE.strftime('%Y%m%d')}-{batch_seq:03d}"
        batch = db.session.query(Batch).filter_by(code=batch_code).first()
        if batch is not None:
            if item_idx == 0 and wh_code == "WH-KH":
                transit_source = (batch, locations[f"{wh_code}/{loc_code}"], qty)
            continue  # 已經建立過，略過（冪等）
        batch = Batch(
            code=batch_code,
            item_id=item.id,
            supplier_id=suppliers[0].id,
            actual_unit_cost=unit_cost,
            quantity=qty,
            in_date=SEED_IN_DATE,
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
                move_type=MOVE_GRN,
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

    # 在途示範：同一批次由中港倉移出 15 件至 TRANSIT（批次剩餘量守恆）
    if transit_source is not None:
        batch, source_location, _ = transit_source
        transit = locations["TRANSIT/TRANSIT"]
        already = (
            db.session.query(StockBalance)
            .filter_by(item_id=items[0].id, batch_id=batch.id, location_id=transit.id)
            .first()
        )
        if already is not None:
            summary.append("在途示範已存在，略過")
        else:
            source_balance = (
                db.session.query(StockBalance)
                .filter_by(item_id=items[0].id, batch_id=batch.id, location_id=source_location.id)
                .first()
            )
            if source_balance is None:
                raise click.ClickException(
                    f"種子資料異常：找不到批次 {batch.code} 於 {source_location.code} 的餘額，"
                    "無法建立在途示範"
                )
            source_balance.qty = source_balance.qty - SEED_TRANSIT_QTY
            db.session.add(
                StockLedger(
                    item_id=items[0].id,
                    batch_id=batch.id,
                    location_id=source_location.id,
                    qty=-SEED_TRANSIT_QTY,
                    move_type=MOVE_TRANSFER_OUT,
                    source_type="SEED",
                    source_id=batch.id,
                    operator_id=operator.id if operator else None,
                    note="種子資料：跨倉調貨移出",
                )
            )
            db.session.add(
                StockLedger(
                    item_id=items[0].id,
                    batch_id=batch.id,
                    location_id=transit.id,
                    qty=SEED_TRANSIT_QTY,
                    move_type=MOVE_TRANSFER_OUT,
                    source_type="SEED",
                    source_id=batch.id,
                    operator_id=operator.id if operator else None,
                    note="種子資料：跨倉調貨在途",
                )
            )
            db.session.add(
                StockBalance(
                    item_id=items[0].id,
                    batch_id=batch.id,
                    location_id=transit.id,
                    qty=SEED_TRANSIT_QTY,
                )
            )
            summary.append(f"建立在途數量示範 {SEED_TRANSIT_QTY} 件")

    write_audit("SEED_EXECUTED", operator=admin, detail="種子資料建立／更新")
    db.session.commit()
    return summary
