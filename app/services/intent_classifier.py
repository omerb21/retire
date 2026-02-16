import re
from enum import Enum

from app.schemas.llm_chat import ChatRequest


class IntentType(str, Enum):
    BUILD_TARGET_PLAN = "build_target_plan"
    ADJUST_PLAN = "adjust_plan"
    TAX_SIMULATION = "tax_simulation"
    RUN_SCENARIO = "run_scenario"
    GENERIC_QA = "generic_qa"
    DATA_REQUEST = "data_request"
    SYSTEM_HEALTH = "system_health"


_SYSTEM_HEALTH_RE = re.compile(
    r"\b(health|diagnostic|diagnostics|status|trace|log|logs|db)\b",
    re.IGNORECASE,
)

_DATA_REQUEST_RE = re.compile(
    r"(?<![a-z0-9])(snapshot|snap|portfolio|accounts?)(?![a-z0-9])",
    re.IGNORECASE,
)

_BUILD_TARGET_PLAN_RE = re.compile(
    r"\b(target\s*plan|retirement\s*plan|build\s*plan)\b",
    re.IGNORECASE,
)

_ADJUST_PLAN_RE = re.compile(
    r"\b(adjust|update)\b.*\b(plan|target)\b|\b(plan|target)\b.*\b(adjust|update)\b",
    re.IGNORECASE,
)

_RUN_SCENARIO_RE = re.compile(
    r"\b(scenario|termination|compare)\b",
    re.IGNORECASE,
)

_TAX_SIMULATION_RE = re.compile(
    r"\b(tax|taxes)\b",
    re.IGNORECASE,
)


def classify_intent(*, user_message: str, request: ChatRequest) -> tuple[IntentType, str]:
    """Stage 3 introduces IntentType as the SSOT for operational intent.

    Existing ChatIntent remains unchanged and is still used for current tools gating.
    For now, IntentType does not change behavior, it is only computed early and traced.

    Regex is allowed only for intent classification. Do not extract parameters, do not infer
    numeric defaults, and do not alter execution based on extracted values in Stage 3.

    Returns:
        (intent_type, rule_hit)
    """

    _ = request

    text = (user_message or "").strip()
    if not text:
        return IntentType.GENERIC_QA, "default:empty"

    lowered = text.lower()

    if (
        _SYSTEM_HEALTH_RE.search(lowered)
        or any(tok in lowered for tok in ("אבחון", "תקלה", "בריאות מערכת", "שגיאה", "500"))
    ):
        return IntentType.SYSTEM_HEALTH, "regex:system_health"

    if (
        _DATA_REQUEST_RE.search(lowered)
        or any(tok in lowered for tok in ("שלוף נתונים", "תראה לי", "החזר מצב לקוח", "רשימת קופות", "סטטוס תיק"))
    ):
        return IntentType.DATA_REQUEST, "regex:data_request"

    if (
        _BUILD_TARGET_PLAN_RE.search(lowered)
        or any(tok in lowered for tok in ("יעד קצבה", "יעד נטו", "בנה תכנית", "תכנית פרישה", "תוכנית פרישה"))
    ):
        return IntentType.BUILD_TARGET_PLAN, "regex:build_target_plan"

    if (
        _ADJUST_PLAN_RE.search(lowered)
        or any(tok in lowered for tok in ("עדכן תכנית", "שנה יעד", "התאם", "כוון מחדש", "אופטימיזציה"))
    ):
        return IntentType.ADJUST_PLAN, "regex:adjust_plan"

    if (
        _RUN_SCENARIO_RE.search(lowered)
        or any(tok in lowered for tok in ("תרחיש", "עזיבת עבודה", "השוואה", "השווה", "סנריו"))
    ):
        return IntentType.RUN_SCENARIO, "regex:run_scenario"

    if (
        _TAX_SIMULATION_RE.search(lowered)
        or any(tok in lowered for tok in ("מס", "סימולציית מס", "מס על מענק", "מס על היוון", "מס על קצבה"))
    ):
        return IntentType.TAX_SIMULATION, "regex:tax_simulation"

    return IntentType.GENERIC_QA, "default"
