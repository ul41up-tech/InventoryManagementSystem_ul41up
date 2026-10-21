"""帳號與角色管理 API（PRD FR-26）。

僅管理員可操作（PRD §4.1 權限矩陣：帳號與角色指派 → 管理員）。
"""

from __future__ import annotations

import datetime as dt

from flask import Blueprint, jsonify, request

from ..auth import current_user, require_roles
from ..extensions import db
from ..models import ALL_ROLES, ROLE_ADMIN, User
from ..security import PasswordTooLongError, hash_password, write_audit
from .helpers import error, text_field

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

MIN_PASSWORD_LENGTH = 8


@users_bp.get("")
@require_roles(ROLE_ADMIN)
def list_users():
    users = db.session.query(User).order_by(User.username).all()
    return jsonify(
        {
            "data": [
                {
                    "id": u.id,
                    "username": u.username,
                    "name": u.name,
                    "role": u.role,
                    "is_active": u.is_active,
                    "must_change_password": u.must_change_password,
                    "locked": bool(
                        u.locked_until and u.locked_until > dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
                    ),
                    "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                }
                for u in users
            ]
        }
    )


@users_bp.post("")
@require_roles(ROLE_ADMIN)
def create_user():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    username, err = text_field(payload, "username", required=True, max_length=50)
    if err:
        return error(err)
    name, err = text_field(payload, "name", required=True, max_length=100)
    if err:
        return error(err)
    role, err = text_field(payload, "role", required=True, max_length=20)
    if err:
        return error(err)
    if role not in ALL_ROLES:
        return error(f"角色必須是其中之一：{', '.join(ALL_ROLES)}")

    raw_password = str(payload.get("password") or "")
    if len(raw_password) < MIN_PASSWORD_LENGTH:
        return error(f"密碼至少 {MIN_PASSWORD_LENGTH} 個字元")
    try:
        password_hash = hash_password(raw_password)
    except PasswordTooLongError as exc:
        return error(str(exc))

    if db.session.query(User).filter_by(username=username).first() is not None:
        return error("帳號已存在", 409)

    user = User(
        username=username,
        name=name,
        role=role,
        password_hash=password_hash,
        must_change_password=True,
    )
    db.session.add(user)
    db.session.flush()
    write_audit("USER_CREATED", doc_type="user", doc_id=user.username, detail=f"角色 {role}")
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username, "role": user.role}), 201


@users_bp.patch("/<int:user_id>")
@require_roles(ROLE_ADMIN)
def update_user(user_id: int):
    """停用／啟用帳號、變更角色、重設密碼。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("請求內容必須是 JSON 物件")

    user = db.session.get(User, user_id)
    if user is None:
        return error("找不到帳號", 404)

    changed: list[str] = []

    if "role" in payload:
        role = str(payload.get("role") or "")
        if role not in ALL_ROLES:
            return error(f"角色必須是其中之一：{', '.join(ALL_ROLES)}")
        if user.role != role:
            user.role = role
            changed.append(f"角色→{role}")

    if "is_active" in payload:
        is_active = bool(payload.get("is_active"))
        if not is_active and user.id == request.user_id if hasattr(request, "user_id") else False:
            pass
        if user.role == ROLE_ADMIN and not is_active:
            admins = db.session.query(User).filter_by(role=ROLE_ADMIN, is_active=True).count()
            if admins <= 1:
                return error("至少需保留一位啟用中的管理員", 409)
        if user.is_active != is_active:
            user.is_active = is_active
            changed.append("停用" if not is_active else "啟用")

    if "password" in payload and payload.get("password"):
        raw_password = str(payload.get("password"))
        if len(raw_password) < MIN_PASSWORD_LENGTH:
            return error(f"密碼至少 {MIN_PASSWORD_LENGTH} 個字元")
        try:
            user.password_hash = hash_password(raw_password)
        except PasswordTooLongError as exc:
            return error(str(exc))
        user.must_change_password = True
        user.failed_attempts = 0
        user.locked_until = None
        changed.append("重設密碼")

    write_audit("USER_UPDATED", doc_type="user", doc_id=user.username, detail="；".join(changed) or "無變更")
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username, "changed": changed})


@users_bp.post("/<int:user_id>/unlock")
@require_roles(ROLE_ADMIN)
def unlock_user(user_id: int):
    """解除登入鎖定。"""
    user = db.session.get(User, user_id)
    if user is None:
        return error("找不到帳號", 404)
    user.failed_attempts = 0
    user.locked_until = None
    write_audit("ACCOUNT_UNLOCKED", operator=user, detail="管理員手動解除鎖定")
    db.session.commit()
    return jsonify({"id": user.id, "ok": True})
