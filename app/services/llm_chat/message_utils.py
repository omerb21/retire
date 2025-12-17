import json
import re

from ...schemas.llm_chat import ChatMessage


def extract_achieved_pension_from_result(tool_result: str) -> float | None:
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

    return 15000.0


def extract_executed_tools_from_history(messages: list[ChatMessage]) -> set[str]:
    executed: set[str] = set()
    tool_indicators = {
        "✅ המערכת יצרה תרחישי פרישה": "RUN_RETIREMENT_SCENARIOS",
        "✅ התרחיש הוחל בהצלחה": "EXECUTE_RETIREMENT_SCENARIO",
        "📋 **בדיקת שלמות נתונים**": "CHECK_DATA_COMPLETENESS",
        "💵 **הערכת מס בפרישה**": "GET_TAX_PROJECTION",
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
