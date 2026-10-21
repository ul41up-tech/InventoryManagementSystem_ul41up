"""一鍵建立本機資料庫環境。

流程（密碼全程不經由對話、也不寫入版本控制）：
1. 從 ``backend/db_password.txt`` 讀取 PostgreSQL 超級使用者密碼（**不顯示、不輸出**）。
2. 建立／更新專用角色 ``ailearn_app`` 與資料庫 ``AILearn``。
3. 產生隨機的應用密鑰、app 角色密碼與種子密碼，寫入 ``backend/.env``（已 gitignore）。
4. 執行 ``flask db upgrade`` 建立 schema、``flask seed`` 寫入種子資料。

用法（在專案根目錄）：
    backend/.venv/Scripts/python.exe backend/tools/setup_database.py

選項：
    --skip-migrate   只建立角色與資料庫，不執行 migration／seed
"""

from __future__ import annotations

import argparse
import os
import secrets
import string
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
PASSWORD_FILE = BACKEND_DIR / "db_password.txt"
ENV_FILE = BACKEND_DIR / ".env"
PLACEHOLDER = "在此貼上密碼"

APP_ROLE = "ailearn_app"
APP_DB = "AILearn"


def read_superuser_password() -> str:
    """從密碼檔讀取密碼。找不到有效內容時直接中止（不猜、不列印）。"""
    if not PASSWORD_FILE.exists():
        raise SystemExit(f"找不到密碼檔：{PASSWORD_FILE}")
    lines = PASSWORD_FILE.read_text(encoding="utf-8").splitlines()
    candidates = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("=") and not line.strip().startswith("#")
    ]
    if not candidates:
        raise SystemExit("密碼檔內沒有內容，請把密碼貼在檔案最後一行。")
    password = candidates[-1]
    if password == PLACEHOLDER or PLACEHOLDER in password:
        raise SystemExit(
            "密碼檔仍是預設佔位文字。請把「在此貼上密碼」換成你的 PostgreSQL 密碼後再執行。"
        )
    return password


def random_secret(length: int = 24, alphabet: str = string.ascii_letters + string.digits) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_database_and_role(superuser_password: str, app_password: str) -> None:
    import psycopg
    from psycopg import sql

    dsn = f"host=127.0.0.1 port=5432 user=postgres dbname=postgres password={superuser_password}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(APP_ROLE), sql.Literal(app_password)
                    )
                )
                print(f"[1/4] 已建立角色 {APP_ROLE}")
            else:
                cur.execute(
                    sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(APP_ROLE), sql.Literal(app_password)
                    )
                )
                print(f"[1/4] 角色 {APP_ROLE} 已存在，已更新密碼")

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (APP_DB,))
            if cur.fetchone() is None:
                # 注意：psycopg 的 sql.Identifier 會自行加引號，勿再手動包引號
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                        sql.Identifier(APP_DB), sql.Identifier(APP_ROLE)
                    )
                )
                print(f"[2/4] 已建立資料庫 {APP_DB}")
            else:
                print(f"[2/4] 資料庫 {APP_DB} 已存在")


def write_env(app_password: str) -> None:
    secret_key = secrets.token_urlsafe(48)
    seed_password = f"Bmad{random_secret(12)}!9"
    content = (
        "# 由 backend/tools/setup_database.py 產生。請勿提交到版控。\n"
        "DATABASE_URL=postgresql+psycopg://"
        f"{APP_ROLE}:{app_password}@127.0.0.1:5432/{APP_DB}\n"
        f"SECRET_KEY={secret_key}\n"
        f"SEED_PASSWORD={seed_password}\n"
        "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n"
        "LOGIN_MAX_ATTEMPTS=5\n"
        "LOGIN_LOCK_MINUTES=15\n"
        "SESSION_HOURS=8\n"
        "FLASK_DEBUG=1\n"
    )
    ENV_FILE.write_text(content, encoding="utf-8", newline="\n")
    print(f"[3/4] 已寫入 {ENV_FILE.relative_to(PROJECT_DIR)}（含隨機密鑰與密碼，不進版控）")


def run_flask(*args: str) -> None:
    python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    env = dict(os.environ)
    env["FLASK_APP"] = "wsgi:app"
    env.pop("FLASK_DEBUG", None)
    result = subprocess.run(
        [str(python), "-m", "flask", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(output.strip()[-1500:])
        raise SystemExit(f"flask {' '.join(args)} 執行失敗（代碼 {result.returncode}）")
    for line in output.strip().splitlines()[-12:]:
        print(f"      {line}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-migrate", action="store_true", help="只建立角色與資料庫")
    args = parser.parse_args()

    print("=== 讀取本機密碼檔（內容不會顯示）===")
    superuser_password = read_superuser_password()
    app_password = f"Ai{random_secret(20)}!7"

    ensure_database_and_role(superuser_password, app_password)
    write_env(app_password)

    if args.skip_migrate:
        print("[4/4] 已略過 migration 與 seed")
        return

    print("[4/4] 執行 schema migration 與種子資料…")
    run_flask("db", "upgrade")
    run_flask("seed")

    print()
    print("=== 完成 ===")
    print(f"資料庫：{APP_DB}（角色 {APP_ROLE}）")
    print("下一步：")
    print("  cd backend && .venv/Scripts/python.exe -m flask --app wsgi run --port 5000")
    print("  cd frontend && npm run dev")


if __name__ == "__main__":
    main()
