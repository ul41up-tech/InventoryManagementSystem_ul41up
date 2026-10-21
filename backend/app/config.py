"""應用設定。敏感值一律從環境變數讀取，不寫死於程式碼。

原則（PRD §4.9 資安、addendum §3）：
- SECRET_KEY 未設定時**啟動即失敗**，不得使用公開已知的預設值。
- SEED_PASSWORD 未設定時**不得**建立種子帳號（避免所有帳號共用公開密碼）。
- 連線字串、密碼一律由環境變數注入，不落於原始碼。
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# 以檔案位置推導 .env 路徑，不依賴目前工作目錄
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DEV_SECRET_KEY = "dev-only-change-me"  # 僅允許在明確的開發模式使用


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"環境變數 {name} 必須是整數，收到 {raw!r}") from exc
    return max(minimum, value)


class Config:
    # --- 資料庫 ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://ailearn_app@127.0.0.1:5432/AILearn"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- 應用 ---
    DEBUG = _bool("FLASK_DEBUG", False)
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    JSON_AS_ASCII = False  # Flask 3.x 已移除此設定，實際設定於 create_app() 的 app.json.ensure_ascii
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_int("SESSION_HOURS", 8))
    MAX_CONTENT_LENGTH = 1024 * 1024  # 1 MiB

    # --- 登入安全 ---
    LOGIN_MAX_ATTEMPTS = _int("LOGIN_MAX_ATTEMPTS", 5, minimum=1)
    LOGIN_LOCK_MINUTES = _int("LOGIN_LOCK_MINUTES", 15, minimum=1)

    # --- CORS（開發時前端走 Vite proxy；正式環境改為明確允許來源）---
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]
    CORS_SUPPORTS_CREDENTIALS = True

    # --- 種子資料（未設定時 seed 指令會明確拒絕執行）---
    SEED_PASSWORD = os.getenv("SEED_PASSWORD", "")

    @classmethod
    def validate(cls) -> None:
        """啟動時檢查必要設定；缺漏時拋出明確錯誤而非靜默使用不安全預設值。"""
        if not cls.SECRET_KEY:
            raise RuntimeError(
                "缺少 SECRET_KEY。請在 backend/.env 設定（產生方式："
                'python -c "import secrets; print(secrets.token_urlsafe(48))"）'
            )
        if cls.SECRET_KEY == DEV_SECRET_KEY and not cls.DEBUG:
            raise RuntimeError("SECRET_KEY 仍是預設值，請先設定正式的隨機密鑰。")


class TestConfig(Config):
    """測試用設定（不需外部服務）。"""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-secret"
    SEED_PASSWORD = "Test@1234"
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCK_MINUTES = 15
