"""產生初始 schema migration（不需資料庫連線）。

以 SQLAlchemy 的 mock engine 將 ``db.metadata`` 編譯為 PostgreSQL DDL，
再輸出成一支 Alembic migration（``op.execute`` 執行 DDL）。

用法（在 backend/ 目錄下）：
    .venv/Scripts/python.exe tools/generate_initial_migration.py

何時需要重跑：只有當 ``app/models.py`` 的表結構改變且尚未產生後續 migration 時。
若已產生後續 migration，請改用 ``flask db migrate -m "..."`` 產生增量 migration。
"""

from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.extensions import db  # noqa: E402
from app import models  # noqa: F401,E402  (確保所有模型都已註冊)

VERSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations", "versions"
)
OUTPUT = os.path.join(VERSIONS_DIR, "0001_initial_schema.py")


def build_ddl() -> tuple[list[str], list[str]]:
    """回傳 (建立語句, 刪除語句)。"""
    dialect = postgresql.dialect()
    creates: list[str] = []
    drops: list[str] = []

    for table in db.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
        # 移除 CREATE TABLE 尾端的分號再統一處理
        ddl = ddl.rstrip(";").strip()
        creates.append(ddl + ";")

        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            index_ddl = str(CreateIndex(index).compile(dialect=dialect)).strip()
            creates.append(index_ddl.rstrip(";") + ";")

    # 由後往前刪除（先刪有外鍵參考的表）
    for table in reversed(list(db.metadata.sorted_tables)):
        drops.append(f"DROP TABLE IF EXISTS {table.name};")

    return creates, drops


def render_module(creates: list[str], drops: list[str]) -> str:
    def block(statements: list[str]) -> str:
        return "\n".join(f"        op.execute(sa.text({s!r}))" for s in statements)

    today = dt.date.today().isoformat()
    return f'''"""initial schema

由 tools/generate_initial_migration.py 產生（SQLAlchemy metadata → PostgreSQL DDL）。
對應 PRD addendum §1.4 的資料模型。

Revision ID: 0001_initial_schema
Revises:
Create Date: {today}
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
{block(creates)}


def downgrade():
{block(drops)}
'''


def main() -> None:
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    creates, drops = build_ddl()
    content = render_module(creates, drops)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"已產生 {OUTPUT}")
    print(f"  建立語句 {len(creates)} 條，刪除語句 {len(drops)} 條")


if __name__ == "__main__":
    main()
