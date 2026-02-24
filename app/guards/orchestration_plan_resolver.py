from __future__ import annotations

import re

from app.guards.advice_domain import AdviceDomain
from app.guards.orchestration_plan import OrchestrationPlan
from app.services.llm_chat.intent_classifier import ChatIntent

_WORD_RE = re.compile(r"[A-Za-z0-9\u0590-\u05FF']+", flags=re.UNICODE)


def _tokenize(text: str) -> set[str]:
    tokens = set()
    for m in _WORD_RE.finditer((text or "").lower()):
        raw = (m.group(0) or "").strip()
        if raw:
            tokens.add(raw)
    return tokens


def _has_any(tokens: set[str], required: set[str]) -> bool:
    return not tokens.isdisjoint(required)


def _has_all(tokens: set[str], required: set[str]) -> bool:
    return required.issubset(tokens)


def resolve_orchestration_plan(
    user_text: str,
    chat_intent: ChatIntent,
    tools_enabled: bool,
    advice_domain: AdviceDomain | None,
) -> OrchestrationPlan:
    if chat_intent == ChatIntent.NO_TOOLS:
        return OrchestrationPlan.NONE

    if chat_intent == ChatIntent.REPORT:
        return OrchestrationPlan.NONE

    if not tools_enabled:
        return OrchestrationPlan.NONE

    tokens = _tokenize(user_text or "")

    # CASHFLOW_ONLY is only triggered for explicit cashflow wording.
    # Do not treat generic retirement analysis/planning phrases as cashflow.
    if ("תזרים" in tokens) or ("cashflow" in tokens):
        return OrchestrationPlan.CASHFLOW_ONLY

    fixation_required_phrases = [
        {"סטטוס", "קיבוע"},
        {"בוצע", "קיבוע"},
        {"קיבוע", "קודם"},
    ]
    for req in fixation_required_phrases:
        if _has_all(tokens, req):
            return OrchestrationPlan.FIXATION_STATUS

    system_snapshot_required_phrases = [
        {"מה", "יש", "במערכת"},
        {"תוצאות", "בפועל"},
        {"תיק", "מסלקה"},
    ]
    for req in system_snapshot_required_phrases:
        if _has_all(tokens, req):
            return OrchestrationPlan.SYSTEM_SNAPSHOT

    return OrchestrationPlan.NONE
