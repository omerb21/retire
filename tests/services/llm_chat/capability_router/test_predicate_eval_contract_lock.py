import re


def test_predicate_eval_payload_contract_is_exact(monkeypatch) -> None:
    import app.services.agent_trace_logger as trace_logger_mod
    from app.services.llm_chat.capability_router.resolver import resolve
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map

    # Use a deterministic fixture map that will emit predicate_eval events.
    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    events: list[dict] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = (trace_id, kwargs)
        events.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    _ = resolve(
        user_text="GET_CLIENT_SNAPSHOT", client_id=1, trace_id="trace_pred_contract"
    )

    pred = [e for e in events if e.get("event_type") == "predicate_eval"]
    assert pred

    for e in pred:
        p = e.get("payload")
        assert isinstance(p, dict)
        assert set(p.keys()) == {"rule_id", "outcome", "params_hash"}
        assert isinstance(p.get("rule_id"), str) and p.get("rule_id")
        assert p.get("outcome") in {True, False}
        assert isinstance(p.get("params_hash"), str)
        assert re.fullmatch(r"[0-9a-f]{64}", p["params_hash"]) is not None
