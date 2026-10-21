"""應用設定。敏感值一律從環境變數讀取，不寫死於程式碼。"""

import os
from datetime import timedelta

from dotenv import load_dotenv

# 讀取 backend/.env（若存在）。Flask CLI 亦會自動載入，此處為非 CLI 啟動（如 python wsgi.py）所需。
load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- 資料庫 ---
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://ailearn_app@127.0.0.1:5432/AILearn"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- 應用 ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JSON_AS_ASCII = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # --- 登入安全 ---
    LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))

    # --- CORS（開發時前端走 Vite proxy；正式環境改為明確允許來源）---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    CORS_SUPPORTS_CREDENTIALS = True

    # --- 種子資料 ---
    SEED_PASSWORD = os.getenv("SEED_PASSWORD", "Bmad@2026")
