from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def _minimal_capability_map() -> dict:
    return {
        "capability_map_version": "test_v1",
        "router_normalization_version": "test_norm_v1",
        "capabilities": [
            {
                "capability_id": "build_target_plan_v1",
                "mode": "ACTION",
                "intent_type": "PLAN",
                "priority": 10,
                "output_schema_id": "qa_answer_v1",
                "tool_chain": [],
                "triggers": {
                    "trigger_terms": ["בנה תכנית", "בנה תוכנית"],
                    "trigger_regex": [],
                    "negative_triggers": [],
                },
            },
            {
                "capability_id": "default_qa_v1",
                "mode": "QA",
                "intent_type": "QA",
                "priority": 0,
                "output_schema_id": "qa_answer_v1",
                "tool_chain": [],
                "triggers": {
                    "trigger_terms": [],
                    "trigger_regex": [],
                    "negative_triggers": [],
                },
            },
        ],
    }


def _disable_trace_logging(monkeypatch) -> None:
    try:
        import app.services.agent_trace_logger as trace_logger

        monkeypatch.setattr(trace_logger, "log_trace_event", lambda *args, **kwargs: None)
    except Exception:
        pass


def test_no_match_returns_default_qa(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)
    _disable_trace_logging(monkeypatch)

    from app.services.llm_chat.capability_router import resolver

    monkeypatch.setattr(resolver, "load_capability_map", lambda: _minimal_capability_map())

    decision = resolver.resolve(
        user_text="טקסט שלא אמור להתאים לשום יכולת",
        client_id=None,
        trace_id=None,
        intent_type=None,
    )

    assert decision.capability_id == "default_qa_v1"


def test_match_returns_expected_capability(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)
    _disable_trace_logging(monkeypatch)

    from app.services.llm_chat.capability_router import resolver

    monkeypatch.setattr(resolver, "load_capability_map", lambda: _minimal_capability_map())

    decision = resolver.resolve(
        user_text="בנה תכנית פרישה בבקשה",
        client_id=None,
        trace_id=None,
        intent_type=None,
    )

    assert decision.capability_id == "build_target_plan_v1"


def test_router_has_no_side_effects(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)
    _disable_trace_logging(monkeypatch)

    from app.services.llm_chat.capability_router import resolver

    monkeypatch.setattr(resolver, "load_capability_map", lambda: _minimal_capability_map())

    d1 = resolver.resolve(
        user_text="טקסט שלא אמור להתאים לשום יכולת",
        client_id=None,
        trace_id=None,
        intent_type=None,
    )
    d2 = resolver.resolve(
        user_text="טקסט שלא אמור להתאים לשום יכולת",
        client_id=None,
        trace_id=None,
        intent_type=None,
    )

    assert d1.capability_id == d2.capability_id
    assert d1 == d2
