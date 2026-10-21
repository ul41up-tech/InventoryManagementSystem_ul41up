"""API 共用輸入處理工具：型別安全、範圍檢查、分頁。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import jsonify, request

MAX_LIMIT = 200
DEFAULT_LIMIT = 50
STOCK_QUERY_MAX_LIMIT = 50  # 與 PRD FR-12／AC-6 一致：查詢結果上限 50 筆

# 金額上限（對應 Numeric(12,2)）
MAX_MONEY = Decimal("99999999.99")
# 比率上限（對應 Numeric(6,4)，0~1）
MAX_RATE = Decimal("1")


def int_arg(name: str, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    """讀取整數查詢參數；非數字或越界時退回預設值，不拋例外。"""
    raw = request.args.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def text_field(payload: dict, key: str, *, required: bool = False, max_length: int | None = None,
               default: str = "") -> tuple[str | None, str | None]:
    """讀取字串欄位並檢查長度。回傳 (值, 錯誤訊息)；錯誤時值為 None。"""
    raw = payload.get(key)
    if raw is None:
        if required:
            return None, f"{key} 為必填欄位"
        return default, None
    if not isinstance(raw, str):
        return None, f"{key} 必須是字串"
    value = raw.strip()
    if required and not value:
        return None, f"{key} 不可為空"
    if max_length is not None and len(value) > max_length:
        return None, f"{key} 長度不可超過 {max_length} 個字元"
    return value, None


def decimal_field(
    payload: dict,
    key: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> tuple[Decimal | None, str | None]:
    """讀取十進位欄位並檢查範圍。回傳 (值, 錯誤訊息)。"""
    raw = payload.get(key)
    if raw is None or raw == "":
        return None, None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None, f"{key} 必須是數字"
    if not value.is_finite():
        return None, f"{key} 必須是有限數值"
    if minimum is not None and value < minimum:
        return None, f"{key} 不可小於 {minimum}"
    if maximum is not None and value > maximum:
        return None, f"{key} 不可大於 {maximum}"
    return value, None


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status
