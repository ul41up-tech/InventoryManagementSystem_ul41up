"""密碼雜湊、登入鎖定判定與稽核紀錄寫入（PRD FR-1、FR-3）。"""

from __future__ import annotations

import datetime as dt

import bcrypt
from flask import current_app

from .extensions import db
from .models import AuditLog, User
from .timeutil import utcnow

# bcrypt 只取前 72 bytes；超長密碼直接拒絕，不靜默截斷
BCRYPT_MAX_BYTES = 72


class PasswordTooLongError(ValueError):
    """密碼超過 bcrypt 上限。"""


def hash_password(raw: str) -> str:
    encoded = raw.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise PasswordTooLongError("密碼長度超過 72 bytes，請改用較短的密碼")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        encoded = raw.encode("utf-8")
    except AttributeError:
        return False
    if len(encoded) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except ValueError:
        return False


def is_locked(user: User) -> bool:
    """帳號是否仍在鎖定期間。鎖定期已過時一併清除失敗次數並留下稽核紀錄。"""
    if user.locked_until is None:
        return False
    if user.locked_until > utcnow():
        return True
    # 鎖定已到期：清空計數，讓下一次失敗重新累積
    user.failed_attempts = 0
    user.locked_until = None
    write_audit("ACCOUNT_UNLOCKED", operator=user, detail="鎖定期已過，帳號自動解鎖")
    return False


def register_failed_attempt(user: User) -> bool:
    """累積失敗次數，超過上限則鎖定。回傳是否觸發鎖定。"""
    user.failed_attempts = (user.failed_attempts or 0) + 1
    limit = max(1, int(current_app.config.get("LOGIN_MAX_ATTEMPTS", 5)))
    if user.failed_attempts >= limit:
        minutes = max(1, int(current_app.config.get("LOGIN_LOCK_MINUTES", 15)))
        user.locked_until = utcnow() + dt.timedelta(minutes=minutes)
        return True
    return False


def reset_failed_attempts(user: User) -> None:
    user.failed_attempts = 0
    user.locked_until = None


def write_audit(
    action: str,
    *,
    operator: User | None = None,
    doc_type: str | None = None,
    doc_id: str | int | None = None,
    item_id: int | None = None,
    batch_id: int | None = None,
    location_id: int | None = None,
    qty=None,
    reason: str | None = None,
    detail: str | None = None,
) -> None:
    """寫入不可刪除的操作紀錄（FR-3）。同一交易內與異動一起 commit。"""
    entry = AuditLog(
        operator_id=operator.id if operator else None,
        operator_name=operator.username if operator else None,
        action=action,
        doc_type=doc_type,
        doc_id=str(doc_id) if doc_id is not None else None,
        item_id=item_id,
        batch_id=batch_id,
        location_id=location_id,
        qty=qty,
        reason=reason,
        detail=(detail or "")[:500] or None,
    )
    db.session.add(entry)
