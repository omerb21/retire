from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.services.llm_chat.capability_router.normalization import (
    normalize_user_text_v1,
    sha256_hex,
)
from app.services.llm_chat.capability_router.runtime_context import RouterDecision
from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
from app.services.llm_chat.orchestration_core.canonical_action_selector import (
    ACTION_ANSWER_GENERAL_QUESTION,
    ACTION_COMPARE_EXISTING_PLANS,
    ACTION_GREETING_AND_MENU,
    ACTION_PLAN_RETIREMENT,
    ACTION_TERMINATION_EXECUTION,
    ACTION_TERMINATION_PRECHECK,
)

_STAGE_C_ROUTER_HARDENING_MAP: dict[str, Any] = {
    "MATCH_PATH": (
        "resolve(): iterates caps_to_scan; uses _match_capability(); selects highest priority"
    ),
    "NO_MATCH_PATH": "resolve(): if selected is None: fallback selection",
    "FALLBACK_HOOKS": [
        "default_cap detection via trigger_regex == ['.*']",
        "fallback based on intent_type + default_cap",
        "fallback to first capability in capability_map",
    ],
}


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
    raw_triggers = cap.get("triggers")
    triggers = raw_triggers if isinstance(raw_triggers, dict) else {}
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
        neg_str = neg if isinstance(neg, str) else ""
        hit = bool(neg_str and (neg_str.lower() in normalized_text))
        neg_params = {"neg": neg} if isinstance(neg, str) else {}
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.negative_trigger",
            outcome=not hit,
            params_hash=_params_hash(neg_params),
        )
        if hit:
            return False

    term_hit = False
    for term in trigger_terms:
        term_str = term if isinstance(term, str) else ""
        hit = bool(term_str and (term_str.lower() in normalized_text))
        term_params = {"term": term} if isinstance(term, str) else {}
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.trigger_term",
            outcome=hit,
            params_hash=_params_hash(term_params),
        )
        if hit:
            term_hit = True
            break

    regex_hit = False
    for pat in trigger_regex:
        rx = _compile_regex(pat)
        search_text = normalized_text or ""
        hit = bool(rx is not None and rx.search(search_text) is not None)
        pattern_params = {"pattern": pat} if isinstance(pat, str) else {}
        _emit_predicate_eval(
            trace_id=trace_id,
            client_id=client_id,
            rule_id=f"{cap_id}.trigger_regex",
            outcome=hit,
            params_hash=_params_hash(pattern_params),
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


def _has_catch_all_trigger(cap: dict[str, Any]) -> bool:
    cap_triggers_raw = cap.get("triggers")
    triggers: dict[str, Any] = {}
    if isinstance(cap_triggers_raw, dict):
        triggers = cap_triggers_raw
    trigger_regex_raw = triggers.get("trigger_regex")
    rx: list[Any] = []
    if isinstance(trigger_regex_raw, list):
        rx = trigger_regex_raw
    return rx == [".*"]


def _filter_caps_by_intent_type(
    capabilities: list[Any], intent_type: str
) -> list[dict[str, Any]]:
    filtered_caps: list[dict[str, Any]] = []
    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        cap_intent_type = str(cap.get("intent_type") or "").strip()
        if cap_intent_type == intent_type:
            filtered_caps.append(cap)
    return filtered_caps


def _filter_readonly_execute_qa_caps(
    capabilities: list[Any],
) -> list[dict[str, Any]]:
    filtered_caps: list[dict[str, Any]] = []
    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        cap_intent_type = str(cap.get("intent_type") or "").strip()
        side_effect_class = str(cap.get("side_effect_class") or "").strip()
        cap_mode = str(cap.get("mode") or "").strip()
        if cap_intent_type != "EXECUTE":
            continue
        if side_effect_class != "READ_ONLY":
            continue
        if cap_mode != "QA":
            continue
        filtered_caps.append(cap)
    return filtered_caps


def _select_highest_priority_match(
    *,
    capabilities: list[dict[str, Any]],
    normalized_text: str,
    trace_id: str | None,
    client_id: int | None,
    selected: dict[str, Any] | None,
    selected_prio: int,
) -> tuple[dict[str, Any] | None, int]:
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
    return selected, selected_prio


def resolve(
    *,
    user_text: str,
    client_id: int | None,
    trace_id: str | None,
    intent_type: str | None = None,
    state_snapshot: dict | None = None,
    last_tool_name: str | None = None,
    canonical_action: str | None = None,
) -> RouterDecision:
    _ = (client_id, state_snapshot, last_tool_name)

    cap_map = load_capability_map()
    capabilities = (
        cap_map.get("capabilities")
        if isinstance(cap_map.get("capabilities"), list)
        else []
    )

    default_cap: dict[str, Any] | None = None
    try:
        last = capabilities[-1] if capabilities else None
        if isinstance(last, dict):
            if _has_catch_all_trigger(last):
                default_cap = last
    except Exception:
        default_cap = None

    if default_cap is None:
        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            if _has_catch_all_trigger(cap):
                default_cap = cap
                break

    normalized_text = normalize_user_text_v1(user_text)
    norm_hash = sha256_hex(normalized_text)

    deterministic_default_cap: dict[str, Any] | None = None
    for cap in capabilities:
        if not isinstance(cap, dict):
            continue
        if cap.get("capability_id") == "default_qa_v1":
            deterministic_default_cap = cap
            break

    selected: dict[str, Any] | None = None
    selected_prio = -(10**9)

    effective_intent_type = intent_type.strip() if isinstance(intent_type, str) else ""
    if not effective_intent_type:
        intent_type_by_action = {
            ACTION_PLAN_RETIREMENT: "PLAN",
            ACTION_TERMINATION_EXECUTION: "EXECUTE",
            ACTION_TERMINATION_PRECHECK: "EXECUTE",
            ACTION_COMPARE_EXISTING_PLANS: "QA",
            ACTION_ANSWER_GENERAL_QUESTION: "QA",
            ACTION_GREETING_AND_MENU: "QA",
        }
        effective_intent_type = str(
            intent_type_by_action.get(str(canonical_action or ""), "")
        ).strip()

    caps_to_scan = capabilities
    if effective_intent_type:
        caps_to_scan = _filter_caps_by_intent_type(capabilities, effective_intent_type)

    selected, selected_prio = _select_highest_priority_match(
        capabilities=caps_to_scan,
        normalized_text=normalized_text,
        trace_id=trace_id,
        client_id=client_id,
        selected=selected,
        selected_prio=selected_prio,
    )

    selected_capability_id = ""
    if isinstance(selected, dict):
        selected_capability_id = str(selected.get("capability_id") or "")

    if str(canonical_action or "") == ACTION_ANSWER_GENERAL_QUESTION and (
        selected is None or selected_capability_id == "default_qa_v1"
    ):
        readonly_execute_caps = _filter_readonly_execute_qa_caps(capabilities)
        selected, selected_prio = _select_highest_priority_match(
            capabilities=readonly_execute_caps,
            normalized_text=normalized_text,
            trace_id=trace_id,
            client_id=client_id,
            selected=selected,
            selected_prio=selected_prio,
        )

    if selected is None:
        if deterministic_default_cap is not None:
            selected = deterministic_default_cap
        elif effective_intent_type and default_cap is not None:
            selected = default_cap
        else:
            selected = None

    capability_id = "unknown"
    mode = "QA"
    tool_chain: list[str] = []
    output_schema_id = "qa_answer_v1"

    if isinstance(selected, dict):
        capability_id = str(selected.get("capability_id") or capability_id)
        mode = str(selected.get("mode") or mode)
        selected_output_schema_id = selected.get("output_schema_id")
        output_schema_id = str(selected_output_schema_id or output_schema_id)

        raw_chain = selected.get("tool_chain")
        if isinstance(raw_chain, list):
            tool_chain = []
            for x in raw_chain:
                if isinstance(x, str) and x:
                    tool_chain.append(str(x))
    else:
        capability_id = ""
        mode = "QA"
        tool_chain = []
        output_schema_id = "SSOT_INVALID_NO_DEFAULT_QA"

    capability_map_version = str(cap_map.get("capability_map_version") or "")
    router_normalization_version = str(
        cap_map.get("router_normalization_version") or ""
    )

    decision = RouterDecision(
        capability_id=capability_id,
        mode=mode,
        tool_chain=tool_chain,
        output_schema_id=output_schema_id,
        capability_map_version=capability_map_version,
        router_normalization_version=router_normalization_version,
        normalized_text_hash=norm_hash,
    )

    try:
        from app.services.agent_trace_logger import log_trace_event

        router_norm_ver = decision.router_normalization_version

        log_trace_event(
            trace_id=trace_id,
            event_type="router_selected",
            payload={
                "capability_id": decision.capability_id,
                "tool_chain": list(decision.tool_chain),
                "output_schema_id": decision.output_schema_id,
                "capability_map_version": decision.capability_map_version,
                "router_normalization_version": router_norm_ver,
                "normalized_text_hash": decision.normalized_text_hash,
            },
            client_id=client_id,
        )
    except Exception:
        pass

    _ = trace_id
    return decision
