import os


def _clear_router_caches() -> None:
    from app.services.llm_chat.capability_router.ssot_loader import (
        load_capability_map,
        load_ssot_v1,
    )

    load_ssot_v1.cache_clear()
    load_capability_map.cache_clear()


def test_intent_classifier_precedence_approve_over_execute(monkeypatch):
    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/capability_map_b2_intent_type.yaml"
    )
    _clear_router_caches()

    from app.services.llm_chat.capability_router.resolver import resolve

    decision = resolve(
        user_text="אשר וגם בצע",
        client_id=None,
        trace_id=None,
        intent_type="APPROVE",
    )
    assert decision.capability_id == "approve_intent_test_v1"


def test_resolver_filters_by_intent_type_and_falls_back_to_default(monkeypatch):
    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/capability_map_b2_intent_type.yaml"
    )
    _clear_router_caches()

    from app.services.llm_chat.capability_router.resolver import resolve

    decision_plan = resolve(
        user_text="doit",
        client_id=None,
        trace_id=None,
        intent_type="PLAN",
    )
    assert decision_plan.capability_id == "default_qa_v1"

    decision_execute = resolve(
        user_text="doit",
        client_id=None,
        trace_id=None,
        intent_type="EXECUTE",
    )
    assert decision_execute.capability_id == "execute_intent_test_v1"
