import re
from datetime import date

from app.models.client import Client
from app.services.llm_chat.orchestration_utils import resolve_target_retirement_age
from app.services.llm_chat.orchestration_utils import (
    compute_retirement_date_from_birth_date,
    extract_explicit_retirement_age_from_text,
    extract_explicit_retirement_date_from_text,
)


def infer_pending_retirement_fields_for_marker(
    *,
    original_user_msg: str,
    db,
    client_id: int | None,
    today,
) -> tuple[int | None, str | None]:
    explicit_date = extract_explicit_retirement_date_from_text(original_user_msg)
    if isinstance(explicit_date, str) and explicit_date.strip():
        resolved_age = extract_explicit_retirement_age_from_text(original_user_msg)
        return resolved_age, explicit_date.strip()

    client_obj = None
    try:
        if client_id is not None:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
    except Exception:
        client_obj = None

    birth_date = getattr(client_obj, "birth_date", None) if client_obj else None
    try:
        if birth_date == date(1970, 1, 1):
            birth_date = None
    except Exception:
        birth_date = None

    now_date = today()
    resolved_age, _src = resolve_target_retirement_age(
        original_user_msg,
        birth_date,
        now_date,
        None,
    )
    if resolved_age is not None and birth_date is not None:
        try:
            resolved_date = compute_retirement_date_from_birth_date(
                birth_date, int(resolved_age)
            ).isoformat()
        except Exception:
            resolved_date = None
        return int(resolved_age), resolved_date

    return resolved_age, None


def infer_retirement_age_for_plan_args(
    *,
    original_user_msg: str,
    client_obj: Client | None,
    pending_payload: dict | None,
    today,
) -> int | None:
    birth_date = getattr(client_obj, "birth_date", None) if client_obj else None
    try:
        if birth_date == date(1970, 1, 1):
            birth_date = None
    except Exception:
        birth_date = None

    resolved_age, _src = resolve_target_retirement_age(
        original_user_msg,
        birth_date,
        today(),
        pending_payload if isinstance(pending_payload, dict) else None,
    )
    return int(resolved_age) if resolved_age is not None else None


def is_tool_error_text(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    raw = value.strip()
    if not raw:
        return False
    lowered = raw.lower()
    return lowered.startswith("tool error:") or lowered.startswith("error:")


def cashflow_missing_target_prompt() -> str:
    return (
        "כדי לחשב תזרים פרישה אני צריך יעד הכנסה חודשי מפורש (ברוטו או נטו).\n\n"
        "דוגמאות להעתקה:\n"
        "יעד נטו: <מספר>\n"
        "יעד ברוטו: <מספר>\n\n"
        "דוגמאות מלאות:\n"
        "יעד נטו: 28000\n"
        "יעד ברוטו: 31000"
    )


def cashflow_missing_age_gender_prompt() -> str:
    return (
        "כדי לחשב תזרים פרישה אני צריך לציין מין וגיל.\n"
        "כתוב למשל:\n"
        "- גבר בן 67\n"
        "- אישה בת 62"
    )


def cashflow_missing_retirement_date_prompt() -> str:
    return (
        "כדי לחשב תזרים פרישה אני צריך תאריך פרישה מפורש בפורמט YYYY-MM-DD.\n\n"
        "כתוב למשל:\n"
        "תאריך פרישה: YYYY-MM-DD"
    )


def has_any_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in (text or ""))


def is_explain_in_words_request(user_msg: str) -> bool:
    normalized = (user_msg or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    cleaned = lowered.replace(".", "").replace("!", "").replace("?", "").strip()
    if cleaned in {"הסבר במילים", "הסבר במילים בלבד", "הסבר במילים בבקשה"}:
        return True
    return False


def is_general_retirement_help_request(user_msg: str) -> bool:
    lowered = (user_msg or "").strip().lower()
    if not lowered:
        return False
    has_domain = any(tok in lowered for tok in ("פרשתי", "פרישה", "פנסיה"))
    has_help = (
        ("עזרה" in lowered)
        or ("איך" in lowered and ("מתכנ" in lowered or "מתכננים" in lowered))
        or ("מה עושים" in lowered and "עכשיו" in lowered)
    )
    if not (has_domain and has_help):
        return False

    # Do not hijack advice-domain flows like tax optimization or investment risk.
    if any(
        tok in lowered
        for tok in (
            "מס",
            "מיסוי",
            "סיכון",
            "מסלול",
            "השקעה",
            "תנודתיות",
            "אגח",
            "מניות",
            "קיבוע",
            "היוון",
            "פיצויים",
        )
    ):
        return False
    has_explicit_calc = any(
        tok in lowered
        for tok in (
            "תזרים",
            "cashflow",
            "דוח",
            'דו"ח',
            "הפק",
            "חשב",
            "תחשב",
            "הרץ",
            "בנה",
            "תכנית",
            "תוכנית",
            "יעד",
            "נטו",
            "ברוטו",
        )
    )
    if has_explicit_calc:
        return False
    return True


def is_general_retirement_intro_request(user_msg: str) -> bool:
    lowered = (user_msg or "").strip().lower()
    if not lowered:
        return False

    has_age = bool(re.search(r"\b(?:בן|בת|גיל)\s*\d{2}\b", lowered))
    has_retired = any(
        tok in lowered for tok in ("סיימתי לעבוד", "סיים לעבוד", "פרשתי", "יצאתי לפנסיה")
    )
    if not (has_age and has_retired):
        return False

    # Do not hijack explicit calculation/tool requests.
    if any(
        tok in lowered
        for tok in (
            "תזרים",
            "cashflow",
            "דוח",
            'דו"ח',
            "יעד",
            "נטו",
            "ברוטו",
            "תכנית",
            "תוכנית",
            "בנה",
            "חשב",
            "תחשב",
            "הרץ",
            "ניתוח",
            "עזיבת עבודה",
            "סיום עבודה",
            "פיצויים",
        )
    ):
        return False

    return True
