"""時間工具：統一使用 UTC 的 naive datetime（對應 DB 的 DateTime 欄位）。"""

from __future__ import annotations

import datetime as dt


def utcnow() -> dt.datetime:
    """回傳 UTC 時間（無時區），取代已棄用的 datetime.utcnow()。"""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
