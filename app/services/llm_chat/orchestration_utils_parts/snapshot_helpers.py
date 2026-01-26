"""Utilities for retirement date and age extraction used by orchestration helpers."""

# NOTE: This module will be filled by move-only extraction from orchestration_utils.py.
# Keep bodies 1:1 when moving functions.

import json
import re
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import Any

from app.services.retirement_age_service import get_retirement_date

try:
    from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67

from app.services.llm_chat.orchestration_utils_parts.protocol import (
    apply_max_exemption_if_requested,
    build_tool_call_message_content,
    parse_tool_call_from_reply,
    validate_tool_call_protocol_for_execution,
)
from app.services.llm_chat.orchestration_utils_parts.tool_names import (
    get_tool_display_name_hebrew,
    normalize_tool_name,
)




def extract_retirement_ages_from_message(user_message: str) -> list[int]:
    if not user_message:
        return []

    text = user_message.lower()

    ages: list[int] = []

    for m in re.finditer(r"גיל\s*(\d{2})", text):
        try:
            ages.append(int(m.group(1)))
        except Exception:
            continue

    for m in re.finditer(r"(?:מול|לעומת|בין|vs|versus)\s*(\d{2})", text):
        try:
            ages.append(int(m.group(1)))
        except Exception:
            continue

    normalized: list[int] = []
    for a in ages:
        if a < 40 or a > 80:
            continue
        if a not in normalized:
            normalized.append(a)

    return normalized

def compute_retirement_date_from_birth_date(birth_date: date, retirement_age: int) -> date:
    try:
        return birth_date + relativedelta(years=int(retirement_age))
    except ValueError:
        return birth_date.replace(
            year=birth_date.year + int(retirement_age),
            day=min(birth_date.day, 28),
        )

def normalize_retirement_date_if_jan1_placeholder(
    retirement_date: str,
    birth_date: date,
    user_message: str,
) -> str:
    if not retirement_date or not birth_date:
        return retirement_date

    try:
        parsed = datetime.strptime(retirement_date, "%Y-%m-%d").date()
    except Exception:
        return retirement_date

    if parsed.month != 1 or parsed.day != 1:
        return retirement_date

    requested_ages = extract_retirement_ages_from_message(user_message)
    if not requested_ages:
        return retirement_date

    implied_age = relativedelta(parsed, birth_date).years

    if implied_age in requested_ages:
        return compute_retirement_date_from_birth_date(birth_date, implied_age).isoformat()

    if len(requested_ages) == 1:
        return compute_retirement_date_from_birth_date(birth_date, requested_ages[0]).isoformat()

    return retirement_date

def compute_default_retirement_date_for_tool_call(*, birth_date: date | None, gender: str | None, user_message: str) -> str:
    if birth_date is None:
        return ""

    try:
        if birth_date == date(1970, 1, 1):
            return ""
    except Exception:
        pass

    if not gender or not str(gender).strip():
        return ""

    requested_ages = extract_retirement_ages_from_message(user_message)
    if len(requested_ages) == 1:
        return compute_retirement_date_from_birth_date(birth_date, requested_ages[0]).isoformat()

    try:
        legal_retirement_date = get_retirement_date(birth_date, str(gender))
    except Exception:
        return ""

    today = date.today()
    if legal_retirement_date < today:
        return today.isoformat()
    return legal_retirement_date.isoformat()

