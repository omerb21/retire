from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


NO_NUMERIC_CLAIMS_WITHOUT_TOOLS_MARKER = "NO_NUMERIC_CLAIMS_WITHOUT_TOOLS"


_FORBIDDEN_PHRASES = [
    "guarantee",
    "guaranteed",
    "בטוח ב-100%",
    "מובטח",
    "אין סיכון",
]


@dataclass(frozen=True)
class QaClaimsGuardResult:
    blocked: bool
    policy_reasons: list[str]


def _contains_any_digit(text: str) -> bool:
    for ch in text:
        if "0" <= ch <= "9":
            return True
    return False


def _normalize_casefold(text: str) -> str:
    return (text or "").casefold()


def _detect_forbidden_claims(text: str) -> bool:
    lowered = _normalize_casefold(text)
    return any(_normalize_casefold(p) in lowered for p in _FORBIDDEN_PHRASES)


def _extract_answer_text(answer_blocks: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    for b in answer_blocks:
        try:
            t = b.get("text")
        except Exception:
            t = None
        if isinstance(t, str) and t:
            parts.append(t)
    return "\n".join(parts)


def _has_required_numeric_marker(answer_blocks: Iterable[dict[str, Any]]) -> bool:
    for b in answer_blocks:
        try:
            b_type = b.get("type")
            b_text = b.get("text")
        except Exception:
            b_type = None
            b_text = None

        if b_type == "caveats" and isinstance(b_text, str) and NO_NUMERIC_CLAIMS_WITHOUT_TOOLS_MARKER in b_text:
            return True

    return False


def evaluate_qa_claims_guard(*, answer_blocks: list[dict[str, Any]]) -> QaClaimsGuardResult:
    answer_text = _extract_answer_text(answer_blocks)

    policy_reasons: list[str] = []

    has_digits = _contains_any_digit(answer_text)
    if has_digits and (not _has_required_numeric_marker(answer_blocks)):
        policy_reasons.append("anchors_missing")

    if _detect_forbidden_claims(answer_text):
        policy_reasons.append("forbidden_claims")

    return QaClaimsGuardResult(blocked=bool(policy_reasons), policy_reasons=policy_reasons)


def guard_qa_answer_payload(
    *,
    qa_answer_payload: dict[str, Any],
    trace_id: str | None,
    client_id: int | None,
    detected_capability_id: str,
) -> dict[str, Any]:
    answer_blocks = []
    try:
        raw = qa_answer_payload.get("answer_blocks")
        if isinstance(raw, list):
            answer_blocks = raw
    except Exception:
        answer_blocks = []

    res = evaluate_qa_claims_guard(answer_blocks=answer_blocks)
    if not res.blocked:
        return qa_answer_payload

    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=trace_id,
            event_type="qa_claims_blocked",
            payload={
                "detected_capability_id": detected_capability_id,
                "policy_reasons": list(res.policy_reasons),
            },
            client_id=client_id,
        )
    except Exception:
        pass

    return build_policy_blocked_partial_result(
        detected_capability_id=detected_capability_id,
        policy_reasons=res.policy_reasons,
    )


def build_policy_blocked_partial_result(
    *,
    detected_capability_id: str,
    policy_reasons: list[str],
) -> dict[str, Any]:
    return {
        "mode": "QA",
        "status": "policy_blocked",
        "detected_capability_id": detected_capability_id,
        "what_ran": [],
        "missing_fields": [],
        "next_step": "adjust_request",
        "policy_reasons": list(policy_reasons),
    }
