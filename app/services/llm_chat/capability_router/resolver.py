from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.services.llm_chat.capability_router.normalization import (
    normalize_user_text_v1, sha256_hex)
from app.services.llm_chat.capability_router.runtime_context import \
    RouterDecision
from app.services.llm_chat.capability_router.ssot_loader import \
    load_capability_map


def _compile_regex(pattern: str) -> re.Pattern[str] | None:
    if not isinstance(pattern, str) or not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except Exception:
        return None


def _sha256_hex_utf8(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _params_hash(params: dict[str, Any] | None) -> str:
    if not params:
        return _sha256_hex_utf8("")
    try:
        stable = json.dumps(
            params, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return _sha256_hex_utf8(stable)
    except Exception:
        return _sha256_hex_utf8("")


def _emit_predicate_eval(
    *,
    trace_id: str | None,
    client_id: int | None,
    rule_id: str,
    outcome: bool,
    params_hash: str,
) -> None:
    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=trace_id,
            event_type="predicate_eval",
            payload={
                "rule_id": str(rule_id or ""),
                "outcome": bool(outcome),
                "params_hash": str(params_hash or ""),
            },
            client_id=client_id,
        )
    except Exception:
        pass


def _match_capability(
    *,
    cap: dict[str, Any],
    normalized_text: str,
    trace_id: str | None,
    client_id: int | None,
) -> bool:
    triggers = cap.get("triggers") if isinstance(cap.get("triggers"), dict) else {}
    trigger_terms = (
        triggers.get("trigger_terms")
        if isinstance(triggers.get("trigger_terms"), list)
        else []
    )
    trigger_regex = (
        triggers.get("trigger_regex")
        if isinstance(triggers.get("trigger_regex"), list)
        else []
    )
    negative_triggers = (
        triggers.get("negative_triggers")
        if isinstance(triggers.get("negative_triggers"), list)
        else []
    )

    cap_id = str(cap.get("capability_id") or "")

    for neg in negative_triggers:
        hit = bool(isinstance(neg, str) and neg and (neg.lower() in normalized_text))
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.negative_trigger",
            outcome=not hit,
            params_hash=_params_hash({"neg": neg} if isinstance(neg, str) else {}),
        )
        if hit:
            return False

    term_hit = False
    for term in trigger_terms:
        hit = bool(isinstance(term, str) and term and (term.lower() in normalized_text))
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.trigger_term",
            outcome=hit,
            params_hash=_params_hash({"term": term} if isinstance(term, str) else {}),
        )
        if hit:
            term_hit = True
            break

    regex_hit = False
    for pat in trigger_regex:
        rx = _compile_regex(pat)
        hit = bool(rx is not None and rx.search(normalized_text or "") is not None)
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.trigger_regex",
            outcome=hit,
            params_hash=_params_hash({"pattern": pat} if isinstance(pat, str) else {}),
        )
        if hit:
            regex_hit = True
            break

    if trigger_terms and trigger_regex:
        return bool(term_hit or regex_hit)
    if trigger_terms:
        return bool(term_hit)
    if trigger_regex:
        return bool(regex_hit)

    return False


def resolve(
    *, user_text: str, client_id: int | None, trace_id: str | None
) -> RouterDecision:
    _ = client_id

    cap_map = load_capability_map()
    capabilities = (
        cap_map.get("capabilities")
        if isinstance(cap_map.get("capabilities"), list)
        else []
    )

    normalized_text = normalize_user_text_v1(user_text)
    norm_hash = sha256_hex(normalized_text)

    selected: dict[str, Any] | None = None
    selected_prio = -(10**9)

    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        if not _match_capability(
            cap=cap,
            normalized_text=normalized_text,
            trace_id=trace_id,
            client_id=client_id,
        ):
            continue

        prio = cap.get("priority")
        prio_val = int(prio) if isinstance(prio, int) else 0
        if selected is None or prio_val > selected_prio:
            selected = cap
            selected_prio = prio_val

    if selected is None and capabilities:
        first = capabilities[0]
        selected = first if isinstance(first, dict) else None

    capability_id = "unknown"
    mode = "QA"
    tool_chain: list[str] = []
    output_schema_id = "qa_answer_v1"

    if isinstance(selected, dict):
        capability_id = str(selected.get("capability_id") or capability_id)
        mode = str(selected.get("mode") or mode)
        output_schema_id = str(selected.get("output_schema_id") or output_schema_id)

        raw_chain = selected.get("tool_chain")
        if isinstance(raw_chain, list):
            tool_chain = [str(x) for x in raw_chain if isinstance(x, str) and x]

    decision = RouterDecision(
        capability_id=capability_id,
        mode=mode,
        tool_chain=tool_chain,
        output_schema_id=output_schema_id,
        capability_map_version=str(cap_map.get("capability_map_version") or ""),
        router_normalization_version=str(
            cap_map.get("router_normalization_version") or ""
        ),
        normalized_text_hash=norm_hash,
    )

    try:
        from app.services.agent_trace_logger import log_trace_event

        log_trace_event(
            trace_id=trace_id,
            event_type="router_selected",
            payload={
                "capability_id": decision.capability_id,
                "tool_chain": list(decision.tool_chain),
                "output_schema_id": decision.output_schema_id,
                "capability_map_version": decision.capability_map_version,
                "router_normalization_version": decision.router_normalization_version,
                "normalized_text_hash": decision.normalized_text_hash,
            },
            client_id=client_id,
        )
    except Exception:
        pass

    _ = trace_id
    return decision
