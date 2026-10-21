"""對真實 PostgreSQL 環境做端對端驗證。

流程：啟動後端 → 以管理員建立/重置專屬測試帳號 → 驗證登入、權限矩陣、
庫存數字、稽核紀錄、改密與登出 → 關閉後端。
密碼從 backend/.env 讀取（不顯示、不輸出）。

用法（在專案根目錄）：
    backend/.venv/Scripts/python.exe backend/tools/verify_live.py
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 5137
BASE = f"http://{HOST}:{PORT}"

PROBE_USER = "verify_probe"
PROBE_PASSWORD = "Verify@2026probe"

failures: list[str] = []


def check(label: str, actual, expected) -> None:
    ok = actual == expected
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}: {actual!r}" + ("" if ok else f"（預期 {expected!r}）"))
    if not ok:
        failures.append(label)


def read_env() -> dict:
    env: dict[str, str] = {}
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        raise SystemExit("找不到 backend/.env，請先執行 backend/tools/setup_database.py")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


class Client:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            BASE + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        try:
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            return exc.code, (json.loads(raw) if raw else None)

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body if body is not None else {})

    def patch(self, path, body):
        return self.request("PATCH", path, body)


def wait_for_server(proc, timeout: int = 40) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.6)
    return False


def main() -> None:
    env = read_env()
    seed_password = env.get("SEED_PASSWORD", "")
    if not seed_password:
        raise SystemExit(".env 內缺少 SEED_PASSWORD")

    python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)

    server_env = dict(os.environ)
    server_env["FLASK_APP"] = "wsgi:app"
    server_env["FLASK_DEBUG"] = "0"
    proc = subprocess.Popen(
        [str(python), "-m", "flask", "--app", "wsgi", "run", "--port", str(PORT), "--no-reload"],
        cwd=str(BACKEND_DIR),
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    try:
        if not wait_for_server(proc):
            print("後端啟動失敗：")
            print((proc.stdout.read() if proc.stdout else "")[-2000:])
            raise SystemExit(1)

        print("=== 1. 健康檢查 ===")
        status, _ = Client().get("/api/health")
        check("GET /api/health", status, 200)

        print("=== 2. 未登入存取受保護端點 ===")
        check("未登入查詢庫存 → 401", Client().get("/api/stock/query")[0], 401)

        print("=== 3. 管理員登入 ===")
        admin = Client()
        status, body = admin.post("/api/auth/login", {"username": "admin", "password": seed_password})
        check("管理員登入成功", status, 200)
        if status != 200:
            raise SystemExit("管理員登入失敗，無法繼續驗證")

        print("=== 4. 帳號管理（FR-26）===")
        status, _ = admin.post(
            "/api/users",
            {
                "username": PROBE_USER,
                "name": "驗證探針",
                "role": "warehouse",
                "password": PROBE_PASSWORD,
            },
        )
        if status == 409:
            users = admin.get("/api/users").get_json()["data"]
            probe = [u for u in users if u["username"] == PROBE_USER][0]
            status, _ = admin.patch(
                f"/api/users/{probe['id']}", {"password": PROBE_PASSWORD, "is_active": True}
            )
            check("測試帳號已重置", status, 200)
        else:
            check("建立測試帳號", status, 201)

        print("=== 5. 登入與鎖定 ===")
        bad = Client()
        check(
            "密碼錯誤 → 401",
            bad.post("/api/auth/login", {"username": PROBE_USER, "password": "wrong"})[0],
            401,
        )

        client = Client()
        status, body = client.post(
            "/api/auth/login", {"username": PROBE_USER, "password": PROBE_PASSWORD}
        )
        check("登入成功", status, 200)
        if status == 200:
            check("角色為 warehouse", body["user"]["role"], "warehouse")
            check("標記需改密", body["user"]["must_change_password"], True)

        print("=== 6. 庫存查詢數字（PRD FR-6／FR-12／AC-5）===")
        status, body = client.get("/api/stock/query?q=IT-000001")
        check("查詢成功", status, 200)
        if status == 200 and body["data"]:
            row = body["data"][0]
            check("在手量（120+30+185+15在途）", row["on_hand"], 350.0)
            check("在途量", row["in_transit"], 15.0)
            check("實體倉合計", row["real_on_hand"], 335.0)
            check("可用量（無配置）", row["available"], 350.0)
            check("ledger 與快取無差額", row["balance_diff"], 0.0)
            check("回應含位置明細", len(row["locations"]) > 0, True)
        else:
            failures.append("查無 IT-000001")

        print("=== 7. 權限矩陣（PRD §4.1）===")
        check("倉管讀供應商 → 403", client.get("/api/suppliers")[0], 403)
        check("倉管讀客戶 → 403", client.get("/api/customers")[0], 403)
        check("倉管讀倉庫 → 403", client.get("/api/warehouses")[0], 403)
        check("倉管讀稽核紀錄 → 403", client.get("/api/audit-logs")[0], 403)
        check("倉管讀庫存 → 200", client.get("/api/stock/query")[0], 200)
        check("倉管讀帳號管理 → 403", client.get("/api/users")[0], 403)

        check("管理員讀稽核紀錄 → 200", admin.get("/api/audit-logs")[0], 200)
        check("管理員建立商品 → 201", admin.post("/api/items", {"name": "驗證測試品"})[0], 201)

        purchasing = Client()
        purchasing.post("/api/auth/login", {"username": "purchasing", "password": seed_password})
        status, body = purchasing.get("/api/customers")
        check("採購讀客戶 → 200（內容遮蔽）", status, 200)
        if status == 200 and body["data"]:
            check("客戶名稱已遮蔽", "不可見" in body["data"][0]["name"], True)
            check("聯絡人已遮蔽", body["data"][0]["contact"], None)

        print("=== 8. 更改密碼與登出 ===")
        status, _ = client.post(
            "/api/auth/change-password",
            {"old_password": PROBE_PASSWORD, "new_password": "Verify@2026probe2"},
        )
        check("改密成功", status, 200)
        again = Client()
        check(
            "新密碼可登入",
            again.post(
                "/api/auth/login", {"username": PROBE_USER, "password": "Verify@2026probe2"}
            )[0],
            200,
        )
        check("登出成功", again.post("/api/auth/logout")[0], 200)
        check("登出後 session 失效", again.get("/api/auth/me")[0], 401)

        print("=== 9. 稽核紀錄（FR-3）===")
        status, body = admin.get("/api/audit-logs?limit=500")
        actions = {r["action"] for r in body["data"]} if status == 200 else set()
        for action in [
            "LOGIN_SUCCESS",
            "LOGIN_FAILED",
            "ITEM_CREATED",
            "ACCESS_DENIED",
            "LOGOUT",
            "PASSWORD_CHANGED",
            "USER_CREATED",
        ]:
            check(f"稽核含 {action}", action in actions, True)

        print()
        if failures:
            print(f"=== 驗證結果：{len(failures)} 項未通過 ===")
            for item in failures:
                print(f"  - {item}")
            raise SystemExit(1)
        print("=== 驗證結果：全部通過 ===")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            proc.kill()


if __name__ == "__main__":
    main()
