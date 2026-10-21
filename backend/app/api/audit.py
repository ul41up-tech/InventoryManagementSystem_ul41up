"""操作紀錄查詢 API（PRD FR-3：任何時間點皆可查出，且不可修改或刪除）。

本模組**只提供讀取**，沒有任何修改或刪除端點。
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import desc, or_, select

from ..auth import require_roles
from ..extensions import db
from ..models import ROLE_ACCOUNTING, ROLE_ADMIN, AuditLog
from .helpers import int_arg

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit-logs")


@audit_bp.get("")
@require_roles(ROLE_ADMIN, ROLE_ACCOUNTING)
def list_audit_logs():
    """依條件查詢操作紀錄（分頁）。"""
    limit = int_arg("limit", default=50, maximum=200)
    offset = int_arg("offset", default=0, maximum=100000)

    stmt = select(AuditLog)
    action = (request.args.get("action") or "").strip()
    operator = (request.args.get("operator") or "").strip()
    keyword = (request.args.get("q") or "").strip()

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if operator:
        stmt = stmt.where(AuditLog.operator_name == operator)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AuditLog.doc_id.ilike(like),
                AuditLog.detail.ilike(like),
                AuditLog.reason.ilike(like),
            )
        )

    total = db.session.scalar(select(db.func.count()).select_from(stmt.subquery())) or 0
    rows = db.session.scalars(stmt.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(limit).offset(offset)).all()

    return jsonify(
        {
            "data": [
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "operator": r.operator_name,
                    "action": r.action,
                    "doc_type": r.doc_type,
                    "doc_id": r.doc_id,
                    "qty": float(r.qty) if r.qty is not None else None,
                    "reason": r.reason,
                    "detail": r.detail,
                }
                for r in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
