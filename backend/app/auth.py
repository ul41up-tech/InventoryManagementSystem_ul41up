"""認證與角色權限（PRD FR-1、FR-2、FR-26）。

權限一律在**伺服器端**檢查；前端隱藏按鈕不算通過（AC-4）。
"""

from __future__ import annotations

import datetime as dt
from functools import wraps

from flask import Blueprint, jsonify, request, session

from .extensions import db
from .models import ALL_ROLES, User
from .security import (
    is_locked,
    register_failed_attempt,
    reset_failed_attempts,
    verify_password,
    write_audit,
)
from .timeutil import utcnow

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

GENERIC_LOGIN_ERROR = "帳號或密碼錯誤"


def request_json() -> dict:
    return request.get_json(silent=True) or {}


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def require_roles(*roles: str):
    """角色裝飾器。未登入 → 401；角色不符 → 403。"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None or not user.is_active:
                return jsonify({"error": "未登入或帳號已停用"}), 401
            if roles and user.role not in roles:
                write_audit(
                    "ACCESS_DENIED",
                    operator=user,
                    detail=f"嘗試存取 {fn.__name__}，角色 {user.role} 不在允許清單 {list(roles)}",
                )
                db.session.commit()
                return jsonify({"error": "權限不足"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@auth_bp.post("/login")
def login():
    payload = request_json()
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"error": "請輸入帳號與密碼"}), 400

    user = db.session.query(User).filter_by(username=username).first()

    if user is None:
        write_audit("LOGIN_FAILED", detail=f"不存在的帳號 {username}")
        db.session.commit()
        return jsonify({"error": GENERIC_LOGIN_ERROR}), 401

    if is_locked(user):
        write_audit("LOGIN_BLOCKED_LOCKED", operator=user, detail="帳號仍處於鎖定狀態")
        db.session.commit()
        return jsonify({"error": "帳號已鎖定，請稍後再試"}), 423

    if not user.is_active:
        write_audit("LOGIN_BLOCKED_INACTIVE", operator=user, detail="帳號已停用")
        db.session.commit()
        return jsonify({"error": "帳號已停用"}), 403

    if not verify_password(password, user.password_hash):
        register_failed_attempt(user)
        write_audit("LOGIN_FAILED", operator=user, detail="密碼錯誤")
        db.session.commit()
        return jsonify({"error": GENERIC_LOGIN_ERROR}), 401

    reset_failed_attempts(user)
    user.last_login_at = utcnow()
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    write_audit("LOGIN_SUCCESS", operator=user)
    db.session.commit()

    return jsonify(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "role": user.role,
                "must_change_password": user.must_change_password,
            }
        }
    )


@auth_bp.post("/logout")
def logout():
    user = current_user()
    if user is not None:
        write_audit("LOGOUT", operator=user)
        db.session.commit()
    session.clear()
    return jsonify({"ok": True})


@auth_bp.get("/me")
@require_roles(*ALL_ROLES)
def me():
    user = current_user()
    return jsonify(
        {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
            "must_change_password": user.must_change_password,
        }
    )
