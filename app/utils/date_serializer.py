"""
Unified date serialization utilities for consistent API responses
"""

import re
from datetime import date, datetime
from typing import Any, Union


def serialize_date_to_iso(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Convert any date-like object to ISO string format (YYYY-MM-DD)

    Args:
        date_obj: Date object, datetime object, or string

    Returns:
        ISO formatted date string (YYYY-MM-DD)
    """
    if date_obj is None:
        return ""

    if isinstance(date_obj, str):
        # Already a string, ensure it's in correct format
        if len(date_obj) >= 10:
            return date_obj[:10]  # Take first 10 chars (YYYY-MM-DD)
        return date_obj

    if hasattr(date_obj, "strftime"):
        return date_obj.strftime("%Y-%m-%d")

    return str(date_obj)


def parse_date_flexible(value: Union[date, datetime, str, None]) -> date:
    if value is None:
        raise ValueError("Empty date")

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    raw = str(value).strip()
    raw = raw.strip("`").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("Empty date")

    if raw.upper() == "YYYY-MM-DD":
        raise ValueError("Placeholder date")

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    if re.match(r"^\d{2}/\d{2}/\d{4}$", raw):
        return datetime.strptime(raw, "%d/%m/%Y").date()

    if re.match(r"^\d{2}-\d{2}-\d{4}$", raw):
        normalized = raw.replace("-", "/")
        return datetime.strptime(normalized, "%d/%m/%Y").date()

    if re.match(r"^\d{8}$", raw):
        if raw.startswith("19") or raw.startswith("20"):
            return datetime.strptime(raw, "%Y%m%d").date()
        return datetime.strptime(raw, "%d%m%Y").date()

    iso = raw
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(iso).date()
    except Exception as e:
        raise ValueError(f"Unsupported date format: {value}") from e


def normalize_date_to_iso(value: Union[date, datetime, str, None]) -> str:
    return parse_date_flexible(value).isoformat()


def serialize_monthly_date(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Convert date to monthly format (YYYY-MM-01) for cashflow data

    Args:
        date_obj: Date object, datetime object, or string

    Returns:
        Monthly date string (YYYY-MM-01)
    """
    if date_obj is None:
        return ""

    if isinstance(date_obj, str):
        if len(date_obj) >= 7:
            year_month = date_obj[:7]  # YYYY-MM
            return f"{year_month}-01"
        return date_obj

    if hasattr(date_obj, "strftime"):
        return date_obj.strftime("%Y-%m-01")

    return str(date_obj)


def extract_year_from_date(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Extract year from any date-like object

    Args:
        date_obj: Date object, datetime object, or string

    Returns:
        Year as string (YYYY)
    """
    if date_obj is None:
        return ""

    if isinstance(date_obj, str):
        return date_obj[:4] if len(date_obj) >= 4 else date_obj

    if hasattr(date_obj, "strftime"):
        return date_obj.strftime("%Y")

    return str(date_obj)[:4]


def normalize_cashflow_row(row: dict) -> dict:
    """
    Normalize a cashflow row to ensure consistent date format

    Args:
        row: Cashflow row dictionary

    Returns:
        Normalized row with date as ISO string
    """
    normalized = dict(row)
    if "date" in normalized:
        normalized["date"] = serialize_monthly_date(normalized["date"])
    return normalized
