import logging
import re
from dataclasses import dataclass

from app.schemas.llm_chat import ChatRequest
from app.utils.llm_chat_log import get_current_request_id
from app.services.llm_chat.execution_only_fallback import build_execution_only_fallback

logger = logging.getLogger("app.llm_chat")

AGENT_MODE = "EXECUTION_ONLY"

BLOCKED_REASON_HAS_QUESTION_MARK = "HAS_QUESTION_MARK"
BLOCKED_REASON_HAS_DECISION_PHRASE = "HAS_DECISION_PHRASE"
BLOCKED_REASON_FORMAT_INVALID = "FORMAT_INVALID"

ALLOWED_INSTRUCTIONS_HEADINGS = {
    "הנחיות לביצוע:",
    "הנחיות למודל המתכנת:",
    "הנחיות טכניות:",
}


def get_execution_only_system_prompt() -> str:
    return (
        "מצב: EXECUTION_ONLY. פלט בלבד, ללא קוד-בלוקים וללא טקסט חופשי מעבר למבנה המחייב.\n"
        "חובה להחזיר בדיוק 4 כותרות ובדיוק בסדר הזה:\n"
        "1) מטרה:\n"
        "2) הנחיות למודל המתכנת:\n"
        "3) קריטריון הצלחה:\n"
        "4) סטטוס: SUCCESS\n\n"
        "כללים קשיחים:\n"
        "- אין סימן שאלה ואין ניסוח שמבקש החלטה מהמשתמש\n"
        "- אם חסר מידע, כתוב הנחות עבודה בתוך 'הנחיות למודל המתכנת' במקום לשאול\n"
        "- דיפ מינימלי בלבד\n"
        "- לא לשנות טסטים קיימים אלא אם נאמר במפורש\n"
        "- להריץ pytest ולעצור בכשל הראשון\n\n"
        "תוכן חובה בתוך 'הנחיות למודל המתכנת':\n"
        "- רשימת קבצים לשינוי או 'לא ידוע עדיין'\n"
        "- צעדים ממוספרים לביצוע\n"
        "- חובה לכלול: curl.exe\n"
        "- חובה לכלול: python -m pytest -q\n"
        "- חובה לכלול: git add, git commit, git push\n"
        "- חובה לכלול לפחות נתיב אחד שמתחיל ב app/ או tests/ או Dockerfile\n"
        "- פקודות PowerShell מוכנות להדבקה\n"
        "- קריטריון הצלחה מדיד\n"
    )


@dataclass(frozen=True)
class ExecutionOnlyViolation(Exception):
    reason: str


def _map_violation_reason_to_blocked_reason(reason: str) -> str:
    r = (reason or "").strip()
    if r == "contains_question_mark":
        return BLOCKED_REASON_HAS_QUESTION_MARK
    if r == "contains_forbidden_phrase":
        return BLOCKED_REASON_HAS_DECISION_PHRASE
    return BLOCKED_REASON_FORMAT_INVALID


_FORBIDDEN_PHRASES = (
    "בחר",
    "האם",
    "האם תרצה",
    "האם אתה",
    "מה דעתך",
    "אפשר גם",
    "נשקול",
    "לבחירתך",
    "אופציה",
    "אשר",
    "תגיד לי",
    "שלח לי",
    "מה אתה מעדיף",
    "a או b",
    "1 או 2",
)

_HEADER_RE = re.compile(
    r"^(מטרה|הנחיות לביצוע|הנחיות למודל המתכנת|הנחיות טכניות|קריטריון הצלחה|סטטוס):",
    flags=re.MULTILINE,
)
_STEP_RE = re.compile(r"^\s*(?:\d+|[א-ת])[\.)]\s+", flags=re.MULTILINE)

_REQUIRED_TECH_TOKENS = ("curl.exe", "pytest", "git")
_REQUIRED_PATH_PREFIXES = ("app/", "tests/", "Dockerfile")


def _has_required_exec_only_tech_payload(text: str) -> bool:
    t = (text or "")
    t_lower = t.lower()
    if not all(tok.lower() in t_lower for tok in _REQUIRED_TECH_TOKENS):
        return False
    if any(pfx.lower() in t_lower for pfx in _REQUIRED_PATH_PREFIXES):
        return True
    return False


def is_execution_only(request: ChatRequest) -> bool:
    try:
        return bool(getattr(request, "executor_only", False))
    except Exception:
        return False


def validate_execution_only_output(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ExecutionOnlyViolation("empty_output")

    if "?" in text:
        raise ExecutionOnlyViolation("contains_question_mark")

    lowered = text.lower()
    for phrase in _FORBIDDEN_PHRASES:
        if phrase in lowered:
            raise ExecutionOnlyViolation("contains_forbidden_phrase")

    lines = [ln.rstrip("\n") for ln in text.splitlines()]
    if not lines:
        raise ExecutionOnlyViolation("invalid_format")

    def _find_line(prefix: str) -> int:
        for i, ln in enumerate(lines):
            if ln.startswith(prefix):
                return i
        return -1

    def _find_instructions_heading_line() -> int:
        for i, ln in enumerate(lines):
            if ln.strip() in ALLOWED_INSTRUCTIONS_HEADINGS:
                return i
        return -1

    idx_goal = _find_line("מטרה:")
    idx_steps = _find_instructions_heading_line()
    idx_criteria = _find_line("קריטריון הצלחה:")
    idx_status = _find_line("סטטוס:")

    if min(idx_goal, idx_steps, idx_criteria, idx_status) < 0:
        raise ExecutionOnlyViolation("missing_required_sections")
    if not (idx_goal < idx_steps < idx_criteria < idx_status):
        raise ExecutionOnlyViolation("invalid_section_order")

    goal_line = lines[idx_goal]
    if goal_line.strip() == "מטרה:" or goal_line.strip().endswith(":"):
        raise ExecutionOnlyViolation("invalid_goal_line")

    steps_block = "\n".join(lines[idx_steps + 1 : idx_criteria]).strip("\n")
    if not steps_block.strip():
        raise ExecutionOnlyViolation("missing_steps")
    if _STEP_RE.search(steps_block) is None:
        raise ExecutionOnlyViolation("steps_not_numbered")

    criteria_block = "\n".join(lines[idx_criteria + 1 : idx_status]).strip("\n")
    if not criteria_block.strip():
        raise ExecutionOnlyViolation("missing_criteria")

    status_line = lines[idx_status].strip()
    if status_line == "סטטוס: SUCCESS":
        if not _has_required_exec_only_tech_payload(text):
            raise ExecutionOnlyViolation("invalid_format")
    elif status_line == "סטטוס: BLOCKED" or status_line.startswith("סטטוס: BLOCKED | סיבה: "):
        pass
    else:
        raise ExecutionOnlyViolation("invalid_status")

    extra_headers = _HEADER_RE.findall(text)
    allowed_instruction_header_names = {
        "הנחיות לביצוע",
        "הנחיות למודל המתכנת",
        "הנחיות טכניות",
    }
    if len(extra_headers) != 4:
        raise ExecutionOnlyViolation("invalid_format")
    if extra_headers[0] != "מטרה":
        raise ExecutionOnlyViolation("invalid_format")
    if extra_headers[1] not in allowed_instruction_header_names:
        raise ExecutionOnlyViolation("invalid_format")
    if extra_headers[2] != "קריטריון הצלחה":
        raise ExecutionOnlyViolation("invalid_format")
    if extra_headers[3] != "סטטוס":
        raise ExecutionOnlyViolation("invalid_format")


def execution_only_success_fallback(user_request_text: str) -> str:
    return build_execution_only_fallback(user_request_text)


def execution_only_blocked(reason: str) -> str:
    safe_reason = (reason or "blocked").strip()
    safe_reason = safe_reason.replace("?", "").strip()

    blocked_reason = _map_violation_reason_to_blocked_reason(safe_reason)

    trace_id = get_current_request_id() or "unknown"
    logger.warning(
        "EXECUTION_ONLY BLOCKED trace_id=%s reason=%s",
        trace_id,
        safe_reason,
    )

    return (
        "מטרה: חסימה עקב פלט שאינו עומד במדיניות EXECUTION_ONLY\n"
        "הנחיות לביצוע:\n"
        "א. תקן את פורמט הפלט כך שיתאים למבנה המחייב\n"
        "ב. הסר כל סימן שאלה או ניסוח שמבקש החלטה מהמשתמש\n"
        "קריטריון הצלחה:\n"
        "- הפלט תואם את המבנה המחייב\n"
        "- אין סימני שאלה ואין ביטויי בקשת החלטה\n"
        f"סטטוס: BLOCKED | סיבה: {blocked_reason}"
    )
