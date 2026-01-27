import json
import re

from ...schemas.llm_chat import ChatMessage


def _normalize_tool_args_for_approval_signature(tool_name: str, tool_args: dict) -> dict:
    if not isinstance(tool_args, dict):
        return {}
    if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
        normalized = dict(tool_args)
        normalized.pop("accounts", None)
        return normalized
    return tool_args


def _approval_signature(tool_name: str, tool_args: dict) -> str:
    normalized = _normalize_tool_args_for_approval_signature(tool_name, tool_args)
    try:
        args_json = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    except Exception:
        args_json = "{}"
    return f"{tool_name}:{args_json}"


def get_tool_call_approval_signature(tool_name: str, tool_args: dict) -> str:
    if not isinstance(tool_name, str):
        return ""
    if not isinstance(tool_args, dict):
        tool_args = {}
    return _approval_signature(tool_name, tool_args)


def extract_achieved_pension_from_result(tool_result: str) -> float | None:
    try:
        parsed = json.loads(tool_result)
        if isinstance(parsed, dict):
            res = parsed.get("result") if isinstance(parsed.get("result"), dict) else None
            if isinstance(res, dict) and res.get("accumulated_pension") is not None:
                try:
                    return float(res.get("accumulated_pension") or 0)
                except Exception:
                    return None
            if parsed.get("accumulated_pension") is not None:
                try:
                    return float(parsed.get("accumulated_pension") or 0)
                except Exception:
                    return None
    except Exception:
        pass

    match = re.search(r"קצבה\s*שהושגה[^:]*:\s*([\d,]+)", tool_result)
    if match:
        value_str = match.group(1).replace(",", "")
        try:
            return float(value_str)
        except ValueError:
            return None

    match = re.search(r"Achieved:\s*([\d,]+)", tool_result)
    if match:
        value_str = match.group(1).replace(",", "")
        try:
            return float(value_str)
        except ValueError:
            return None
    return None


def extract_gross_income_for_tax(tool_name: str, tool_result: str) -> float | None:
    if tool_name == "BUILD_TARGET_PENSION_PLAN":
        return extract_achieved_pension_from_result(tool_result)

    if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
        try:
            data = json.loads(tool_result)
            value = data.get("total_guaranteed_income")
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    return None


def extract_target_pension_from_message(message: str) -> float:
    normalized = message.replace(",", "").replace("₪", "").replace('ש"ח', "")

    patterns = [
        r"יעד\s*(?:נטו|ברוטו)\s*[:=\-]?\s*(\d{4,6})",
        r"(\d+)\s*[kK]\s*(?:נטו|לחודש|חודשי|בחודש)?",
        r"(\d{4,6})\s*(?:נטו|לחודש|חודשי|בחודש)",
        r"קצבה\s*(?:של|בגובה|בסך)\s*(\d+)",
        r"יעד\s*(?:של|בגובה|בסך)?\s*(\d+)",
        r"זקוק\s*ל[־-]?\s*(\d+)",
        r"(\d+)\s*אלף",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if "k" in pattern.lower() or "אלף" in pattern:
                value *= 1000
            if value < 100:
                value *= 1000
            if 1000 <= value <= 100000:
                return value

    return 0.0


def extract_latest_target_pension_plan_payload(messages: list[ChatMessage]) -> dict | None:
    marker = "###TARGET_PENSION_PLAN_DATA###"
    end_marker = "###END_TARGET_PENSION_PLAN_DATA###"
    if not messages:
        return None

    for msg in reversed(messages):
        content = getattr(msg, "content", "") or ""
        if marker not in content or end_marker not in content:
            continue
        start = content.rfind(marker)
        end = content.find(end_marker, start + len(marker))
        if start < 0 or end < 0 or end <= start:
            continue
        json_str = content[start + len(marker) : end].strip()
        if not json_str:
            continue
        try:
            parsed = json.loads(json_str)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_executed_tools_from_history(messages: list[ChatMessage]) -> set[str]:
    executed: set[str] = set()
    tool_indicators = {
        "✅ המערכת יצרה תרחישי פרישה": "RUN_RETIREMENT_SCENARIOS",
        "✅ התרחיש הוחל בהצלחה": "EXECUTE_RETIREMENT_SCENARIO",
        "📋 **בדיקת שלמות נתונים**": "CHECK_DATA_COMPLETENESS",
        "💵 **הערכת מס בפרישה**": "GET_TAX_PROJECTION",
        "📌 **פרמטרי מס (שנה)**": "GET_TAX_PARAMS",
        "✅ **נמצא תרחיש שמגיע ליעד": "SELECT_TARGET_PENSION_SCENARIO",
        "✅ **התכנית הושלמה בהצלחה**": "BUILD_TARGET_PENSION_PLAN",
        "ניתוח רגישות": "FIND_OPTIMAL_SCENARIO",
    }

    for msg in messages:
        if msg.role == "assistant":
            for indicator, tool_name in tool_indicators.items():
                if indicator in msg.content:
                    executed.add(tool_name)

    return executed


def find_last_user_message(messages: list[ChatMessage]) -> str:
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


def extract_latest_approval_request(
    messages: list[ChatMessage],
) -> tuple[str, dict] | None:
    ui_marker = "###UI_ACTION###"
    ui_end = "###END_UI_ACTION###"
    for msg in reversed(messages or []):
        if getattr(msg, "role", None) != "assistant":
            continue
        content = getattr(msg, "content", "") or ""
        if ui_marker not in content or ui_end not in content:
            continue
        start = content.find(ui_marker)
        end = content.find(ui_end)
        if start < 0 or end < 0 or end <= start:
            continue
        json_str = content[start + len(ui_marker) : end].strip()
        try:
            parsed = json.loads(json_str)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        if parsed.get("type") != "ui_actions":
            continue
        actions = parsed.get("actions")
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "approval_request":
                continue
            tool_name = action.get("tool_name")
            tool_args = action.get("arguments")
            if isinstance(tool_name, str) and isinstance(tool_args, dict):
                return tool_name, tool_args


def is_undo_intent_text(user_message: str | None) -> bool:
    lowered = (user_message or "").strip().lower()
    if not lowered:
        return False
    triggers = (
        "בטל פעולה",
        "בטל את הפעולה",
        "חזור אחורה",
        "שחזר מצב קודם",
        "undo",
    )
    return any(t in lowered for t in triggers)



def is_user_approval_intent_text(text: str) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return False
    approval_tokens = (
        "אשר",
        "מאשר",
        "אני מאשר",
        "מאשרת",
        "אני מאשרת",
        "approve",
        "approved",
        "ok",
        "כן",
    )
    return raw in approval_tokens


def was_tool_call_previously_approved(
    messages: list[ChatMessage],
    *,
    tool_name: str,
    tool_args: dict,
) -> bool:
    if not isinstance(tool_name, str) or not tool_name.strip():
        return False
    if not isinstance(tool_args, dict):
        return False

    expected = _approval_signature(tool_name, tool_args)
    marker = "###USER_APPROVED###"
    for msg in messages or []:
        if getattr(msg, "role", None) != "user":
            continue
        content = getattr(msg, "content", "") or ""
        if marker not in content:
            continue
        after = content.split(marker, 1)[1].strip()
        json_str = after.strip("`").strip()
        json_str = json_str.splitlines()[0] if json_str else ""
        if not json_str:
            continue
        try:
            parsed = json.loads(json_str)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        approved_tool = parsed.get("tool_name")
        approved_args = parsed.get("arguments")
        if not isinstance(approved_tool, str) or not isinstance(approved_args, dict):
            continue
        if _approval_signature(approved_tool, approved_args) == expected:
            return True
    return False


def extract_user_approval_for_tool_call(
    messages: list[ChatMessage],
) -> tuple[str, dict] | None:
    last_user = find_last_user_message(messages)
    marker = "###USER_APPROVED###"
    if marker not in (last_user or ""):
        return None

    after = last_user.split(marker, 1)[1].strip()
    json_str = after.strip("`").strip()
    json_str = json_str.splitlines()[0] if json_str else ""
    if not json_str:
        return None

    try:
        parsed = json.loads(json_str)
    except Exception:
        return None

    if not isinstance(parsed, dict):
        return None

    tool_name = parsed.get("tool_name")
    tool_args = parsed.get("arguments")
    if not isinstance(tool_name, str):
        return None
    if not isinstance(tool_args, dict):
        return None

    latest_request = extract_latest_approval_request(messages)
    if latest_request is not None:
        requested_tool, requested_args = latest_request
        if _approval_signature(tool_name, tool_args) != _approval_signature(
            requested_tool, requested_args
        ):
            return None

    return tool_name, tool_args


def extract_user_cancel_for_tool_call(
    messages: list[ChatMessage],
) -> tuple[str, dict] | None:
    last_user = find_last_user_message(messages)
    marker = "###USER_CANCELLED###"
    if marker not in (last_user or ""):
        return None

    after = last_user.split(marker, 1)[1].strip()
    json_str = after.strip("`").strip()
    json_str = json_str.splitlines()[0] if json_str else ""
    if not json_str:
        return None

    try:
        parsed = json.loads(json_str)
    except Exception:
        return None

    if not isinstance(parsed, dict):
        return None

    tool_name = parsed.get("tool_name")
    tool_args = parsed.get("arguments")
    if not isinstance(tool_name, str):
        return None
    if not isinstance(tool_args, dict):
        return None

    latest_request = extract_latest_approval_request(messages)
    if latest_request is not None:
        requested_tool, requested_args = latest_request
        if _approval_signature(tool_name, tool_args) != _approval_signature(
            requested_tool, requested_args
        ):
            return None

    return tool_name, tool_args
