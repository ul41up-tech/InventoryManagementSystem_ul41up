"""密碼雜湊、登入鎖定判定與稽核紀錄寫入（PRD FR-1、FR-3）。"""

from __future__ import annotations

import datetime as dt

import bcrypt
from flask import current_app

from .extensions import db
from .models import AuditLog, User
from .timeutil import utcnow


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def is_locked(user: User) -> bool:
    if user.locked_until is None:
        return False
    return user.locked_until > utcnow()


def register_failed_attempt(user: User) -> None:
    """累積失敗次數，超過上限則鎖定。"""
    user.failed_attempts = (user.failed_attempts or 0) + 1
    limit = current_app.config.get("LOGIN_MAX_ATTEMPTS", 5)
    if user.failed_attempts >= limit:
        minutes = current_app.config.get("LOGIN_LOCK_MINUTES", 15)
        user.locked_until = utcnow() + dt.timedelta(minutes=minutes)
        db.session.commit()


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
        detail=detail,
    )
    db.session.add(entry)
