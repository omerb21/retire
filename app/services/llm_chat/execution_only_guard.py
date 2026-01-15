import logging
import re
from dataclasses import dataclass

from app.schemas.llm_chat import ChatRequest
from app.utils.llm_chat_log import get_current_request_id

logger = logging.getLogger("app.llm_chat")

AGENT_MODE = "EXECUTION_ONLY"

BLOCKED_REASON_HAS_QUESTION_MARK = "HAS_QUESTION_MARK"
BLOCKED_REASON_HAS_DECISION_PHRASE = "HAS_DECISION_PHRASE"
BLOCKED_REASON_FORMAT_INVALID = "FORMAT_INVALID"


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

_HEADER_RE = re.compile(r"^(מטרה|הנחיות לביצוע|קריטריון הצלחה|סטטוס):", flags=re.MULTILINE)
_STEP_RE = re.compile(r"^\s*(?:\d+|[א-ת])[\.)]\s+", flags=re.MULTILINE)


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

    idx_goal = _find_line("מטרה:")
    idx_steps = _find_line("הנחיות לביצוע:")
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
    if status_line not in {"סטטוס: SUCCESS", "סטטוס: BLOCKED"}:
        raise ExecutionOnlyViolation("invalid_status")

    extra_headers = _HEADER_RE.findall(text)
    if len(extra_headers) < 4:
        raise ExecutionOnlyViolation("invalid_format")


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
