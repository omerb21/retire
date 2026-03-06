from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.llm_chat.message_utils import is_user_approval_intent_text
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    _is_target_pension_plan_request_text,
    is_portfolio_analysis_request,
    is_process_termination_request,
    is_retirement_cashflow_request,
    is_retirement_comparison_request,
)

ACTION_GREETING_AND_MENU = "ACTION_GREETING_AND_MENU"
ACTION_ANSWER_GENERAL_QUESTION = "ACTION_ANSWER_GENERAL_QUESTION"
ACTION_PLAN_RETIREMENT = "ACTION_PLAN_RETIREMENT"
ACTION_COMPARE_EXISTING_PLANS = "ACTION_COMPARE_EXISTING_PLANS"
ACTION_TERMINATION_PRECHECK = "ACTION_TERMINATION_PRECHECK"
ACTION_TERMINATION_EXECUTION = "ACTION_TERMINATION_EXECUTION"

_CANONICAL_ACTIONS = frozenset(
    {
        ACTION_GREETING_AND_MENU,
        ACTION_ANSWER_GENERAL_QUESTION,
        ACTION_PLAN_RETIREMENT,
        ACTION_COMPARE_EXISTING_PLANS,
        ACTION_TERMINATION_PRECHECK,
        ACTION_TERMINATION_EXECUTION,
    }
)

_GREETING_MESSAGES = frozenset(
    {
        "שלום",
        "היי",
        "הי",
        "בוקר טוב",
        "ערב טוב",
        "צהריים טובים",
        "אפשר עזרה",
        "צריך עזרה",
        "hello",
        "hi",
        "hey",
    }
)

_GREETING_PREFIXES = frozenset(
    {
        "שלום",
        "היי",
        "הי",
        "בוקר טוב",
        "ערב טוב",
        "hello",
        "hi",
        "hey",
    }
)

_GENERAL_QUESTION_PATTERNS = (
    "מה זה",
    "איך עובד",
    "איך זה עובד",
    "מה חשוב לדעת",
    "מה ההבדל",
    "מה האפשרויות",
    "מה אתה יכול להמליץ",
    "מה אפשר",
    "קיבוע זכויות",
    "מה יתן",
    "מה ייתן",
)

_PLANNING_HINTS = (
    "בוא נבדוק",
    "בואי נבדוק",
    "מה יקרה אם",
    "סימולציה",
    "סימולטור",
    "תרחיש",
    "תרחישים",
    "תכנית פרישה",
    "תוכנית פרישה",
    "בנה תכנית",
    "בנה תוכנית",
    "קצבת יעד",
    "יעד נטו",
    "יעד ברוטו",
    "בחינת אפשרויות",
)

_COMPARE_HINTS = (
    "השווה",
    "תשווה",
    "להשוות",
    "השוואה",
    "compare",
    "מה עדיף",
    "בין התכנית",
    "בין התוכנית",
)

_WEAK_NON_EXECUTION_HINTS = (
    "תבדוק",
    "תסביר",
    "תראה",
    "מה כדאי",
    "נבנה",
    "נשווה",
    "בוא נבדוק",
    "סימולציה",
)


@dataclass(frozen=True)
class CanonicalActionDecision:
    action: str
    reason_code: str
    source_signals: tuple[str, ...] = ()


def is_canonical_action(action: str | None) -> bool:
    return isinstance(action, str) and action in _CANONICAL_ACTIONS


def _normalized_state_snapshot(state_snapshot: dict | None) -> dict:
    if isinstance(state_snapshot, dict):
        return state_snapshot
    return {}


def _normalize_legacy_action(action: str | None) -> str:
    mapping = {
        "ACTION_GREETING_AND_NEXT_STEP": ACTION_GREETING_AND_MENU,
        "ACTION_TERMINATION_EXECUTE": ACTION_TERMINATION_EXECUTION,
        "ACTION_TERMINATION_EXECUTION": ACTION_TERMINATION_EXECUTION,
        "ACTION_TERMINATION_PRECHECK": ACTION_TERMINATION_PRECHECK,
        "ACTION_COMPARE_PLANS": ACTION_COMPARE_EXISTING_PLANS,
        "ACTION_BUILD_TARGET_PENSION_PLAN_PLANNING": ACTION_PLAN_RETIREMENT,
        "ACTION_PORTFOLIO_ANALYSIS_SUMMARY": ACTION_ANSWER_GENERAL_QUESTION,
        "ACTION_GENERAL_RECOMMENDATIONS": ACTION_ANSWER_GENERAL_QUESTION,
        "ACTION_FIXATION_EXPLAINER": ACTION_ANSWER_GENERAL_QUESTION,
        "ACTION_OPTIONS_EXPLAINER": ACTION_ANSWER_GENERAL_QUESTION,
        "ACTION_ANSWER_GENERAL_QUESTION": ACTION_ANSWER_GENERAL_QUESTION,
    }
    normalized = mapping.get(str(action or "").strip())
    if normalized in _CANONICAL_ACTIONS:
        return normalized
    return ACTION_ANSWER_GENERAL_QUESTION


def _is_greeting(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if lowered in _GREETING_MESSAGES:
        return True
    return any(lowered.startswith(prefix) for prefix in _GREETING_PREFIXES)


def _has_professional_content(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False
    professional_tokens = (
        "פרישה",
        "קצבה",
        "פנסיה",
        "מס",
        "פיצויים",
        "קיבוע",
        "זכויות",
        "תכנית",
        "תוכנית",
        "תיק",
        "תרחיש",
        "יעד",
    )
    return any(token in lowered for token in professional_tokens)


def _is_general_professional_question(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered or not _has_professional_content(user_text):
        return False
    if _is_compare_request(user_text) or _is_planning_request(user_text):
        return False
    return ("?" in lowered) or any(pattern in lowered for pattern in _GENERAL_QUESTION_PATTERNS)


def _is_compare_request(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False
    if is_retirement_comparison_request(user_text):
        return True
    if any(hint in lowered for hint in _COMPARE_HINTS):
        return True
    return bool(re.search(r"בין.+לבין", lowered))


def _has_explicit_termination_execution_request(user_text: str) -> bool:
    lowered = (user_text or "").lower()
    if not is_process_termination_request(user_text):
        return False
    if any(token in lowered for token in _WEAK_NON_EXECUTION_HINTS):
        return False
    execute_tokens = (
        "בצע",
        "תבצע",
        "הפעל",
        "להפעיל",
        "אני רוצה לבצע",
        "לבצע עכשיו",
        "בצע עכשיו",
        "עדכן במערכת",
        "עדכן",
        "לעדכן",
        "אני מאשר",
        "אני מאשרת",
        "מאשר",
        "מאשרת",
        "execute",
        "apply",
        "run",
        "process_termination",
    )
    return any(token in lowered for token in execute_tokens)


def _has_termination_approval_context(user_text: str, state_snapshot: dict | None) -> bool:
    lowered = (user_text or "").lower()
    state = _normalized_state_snapshot(state_snapshot)

    if "###user_approved###" in lowered and "process_termination" in lowered:
        return True

    approved_tool_name = str(
        state.get("approved_tool_name")
        or state.get("pending_approval_tool_name")
        or state.get("tool_name_pending_approval")
        or ""
    ).strip()
    if approved_tool_name == "PROCESS_TERMINATION":
        if "###user_approved###" in lowered:
            return True
        if bool(state.get("user_approved")):
            return True
        if is_user_approval_intent_text(user_text):
            return True

    if bool(state.get("approval_request_already_sent")) and is_user_approval_intent_text(
        user_text
    ):
        return True

    if bool(state.get("termination_approved")):
        return True

    return False


def _is_planning_request(user_text: str) -> bool:
    lowered = (user_text or "").strip().lower()
    if not lowered:
        return False
    if _is_compare_request(user_text):
        return False
    if bool(_is_target_pension_plan_request_text(user_text)):
        return True
    if bool(is_retirement_cashflow_request(user_text)):
        return True
    return any(hint in lowered for hint in _PLANNING_HINTS)


def select_canonical_action(
    *,
    user_text: str,
    state_snapshot: dict | None = None,
    last_tool_name: str | None = None,
) -> CanonicalActionDecision:
    lowered = (user_text or "").strip().lower()
    state = _normalized_state_snapshot(state_snapshot)

    existing_action = state.get("canonical_action")
    if isinstance(existing_action, str) and existing_action.strip():
        normalized_existing = _normalize_legacy_action(existing_action)
        return CanonicalActionDecision(
            action=normalized_existing,
            reason_code="state_snapshot_canonical_action",
            source_signals=("state_snapshot.canonical_action",),
        )

    compare_request = _is_compare_request(user_text)
    planning_request = _is_planning_request(user_text)
    general_question = _is_general_professional_question(user_text)
    greeting_request = _is_greeting(user_text) and not (
        compare_request or planning_request or general_question
    )

    if _has_termination_approval_context(user_text, state) and is_user_approval_intent_text(
        user_text
    ):
        return CanonicalActionDecision(
            action=ACTION_TERMINATION_EXECUTION,
            reason_code="explicit_termination_execution_approved",
            source_signals=(
                "termination.approval_context",
                "user.approval_intent",
            ),
        )

    if _has_explicit_termination_execution_request(user_text):
        if _has_termination_approval_context(user_text, state):
            return CanonicalActionDecision(
                action=ACTION_TERMINATION_EXECUTION,
                reason_code="explicit_termination_execution_approved",
                source_signals=(
                    "termination.explicit_execution",
                    "termination.approval_context",
                ),
            )
        return CanonicalActionDecision(
            action=ACTION_TERMINATION_PRECHECK,
            reason_code="explicit_termination_execution_missing_approval",
            source_signals=("termination.explicit_execution",),
        )

    if compare_request:
        return CanonicalActionDecision(
            action=ACTION_COMPARE_EXISTING_PLANS,
            reason_code="compare_existing_plans",
            source_signals=("compare.detected",),
        )

    if planning_request:
        return CanonicalActionDecision(
            action=ACTION_PLAN_RETIREMENT,
            reason_code="planning_or_simulation_request",
            source_signals=("planning.detected",),
        )

    if is_process_termination_request(user_text):
        return CanonicalActionDecision(
            action=ACTION_TERMINATION_PRECHECK,
            reason_code="termination_discussion",
            source_signals=("termination.detected",),
        )

    if general_question:
        return CanonicalActionDecision(
            action=ACTION_ANSWER_GENERAL_QUESTION,
            reason_code="general_professional_question",
            source_signals=("general_question.detected",),
        )

    if greeting_request:
        return CanonicalActionDecision(
            action=ACTION_GREETING_AND_MENU,
            reason_code="greeting_detected",
            source_signals=("greeting.detected",),
        )

    if is_portfolio_analysis_request(user_text):
        return CanonicalActionDecision(
            action=ACTION_ANSWER_GENERAL_QUESTION,
            reason_code="portfolio_analysis_generalized",
            source_signals=("portfolio_analysis.detected",),
        )

    if isinstance(last_tool_name, str) and last_tool_name.strip():
        return CanonicalActionDecision(
            action=ACTION_ANSWER_GENERAL_QUESTION,
            reason_code="followup_after_tool",
            source_signals=("last_tool_result.present",),
        )

    if lowered:
        return CanonicalActionDecision(
            action=ACTION_ANSWER_GENERAL_QUESTION,
            reason_code="general_question_default",
            source_signals=("user_text.present",),
        )

    return CanonicalActionDecision(
        action=ACTION_GREETING_AND_MENU,
        reason_code="empty_input_default",
        source_signals=("empty_input",),
    )
