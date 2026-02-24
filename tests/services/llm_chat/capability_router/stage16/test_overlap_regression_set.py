from __future__ import annotations

import os
from typing import Any

import yaml


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def _normalize(text: str) -> str:
    from app.services.llm_chat.capability_router.normalization import \
        normalize_user_text_v1

    return normalize_user_text_v1(text)


def _compile_regex(pattern: str):
    import re

    if not isinstance(pattern, str) or not pattern:
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except Exception:
        return None


def _predicate_outcome_for_cap(
    *, cap: dict[str, Any], normalized_text: str
) -> tuple[bool, bool]:
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

    negative_fired = False
    for neg in negative_triggers:
        if isinstance(neg, str) and neg and (neg.lower() in normalized_text):
            negative_fired = True
            break

    if negative_fired:
        return False, True

    term_hit = False
    for term in trigger_terms:
        if isinstance(term, str) and term and (term.lower() in normalized_text):
            term_hit = True
            break

    regex_hit = False
    for pat in trigger_regex:
        rx = _compile_regex(pat)
        if rx is not None and rx.search(normalized_text or "") is not None:
            regex_hit = True
            break

    if trigger_terms and trigger_regex:
        return bool(term_hit or regex_hit), False
    if trigger_terms:
        return bool(term_hit), False
    if trigger_regex:
        return bool(regex_hit), False

    return False, False


def test_stage16_overlap_regression_set(monkeypatch, client) -> None:
    from app.services.llm_chat.capability_router.resolver import resolve
    from app.services.llm_chat.capability_router.ssot_loader import \
        load_capability_map

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    cap_map = load_capability_map()
    caps = (
        cap_map.get("capabilities")
        if isinstance(cap_map.get("capabilities"), list)
        else []
    )

    fixture = _load_yaml("tests/fixtures/stage16/overlap_inputs.yaml")
    inputs = fixture.get("inputs") if isinstance(fixture.get("inputs"), list) else []
    assert inputs

    for item in inputs:
        input_id = str(item.get("input_id") or "")
        user_text = str(item.get("user_text") or "")
        expected = (
            item.get("expected") if isinstance(item.get("expected"), dict) else {}
        )

        decision = resolve(
            user_text=user_text, client_id=int(client.id), trace_id=f"trace_{input_id}"
        )
        if decision.capability_id != expected.get("capability_id"):
            if (
                os.getenv("CAPABILITY_ROUTER_INTENTIONAL_ROUTING_CHANGE") or ""
            ).strip() == "1":
                continue
            raise AssertionError(
                "Routing snapshot mismatch. Routing changes require version bump + intentional flag + release note. "
                f"input_id={input_id} expected={expected.get('capability_id')} got={decision.capability_id}"
            )

        normalized = _normalize(user_text)

        negative_triggers_fired: list[str] = []
        predicate_outcomes: dict[str, bool] = {}
        for cap in caps:
            if not isinstance(cap, dict):
                continue
            cap_id = str(cap.get("capability_id") or "")
            outcome, neg_fired = _predicate_outcome_for_cap(
                cap=cap, normalized_text=normalized
            )
            predicate_outcomes[cap_id] = bool(outcome)
            if neg_fired:
                negative_triggers_fired.append(cap_id)

        expected_neg = (
            expected.get("negative_triggers_fired")
            if isinstance(expected.get("negative_triggers_fired"), list)
            else []
        )
        expected_pred = (
            expected.get("predicate_outcomes")
            if isinstance(expected.get("predicate_outcomes"), dict)
            else {}
        )

        if (
            negative_triggers_fired != [str(x) for x in expected_neg]
            or predicate_outcomes != expected_pred
        ):
            if (
                os.getenv("CAPABILITY_ROUTER_INTENTIONAL_ROUTING_CHANGE") or ""
            ).strip() == "1":
                continue
            raise AssertionError(
                "Routing metadata snapshot mismatch. Changes require version bump + intentional flag + release note. "
                f"input_id={input_id}"
            )
