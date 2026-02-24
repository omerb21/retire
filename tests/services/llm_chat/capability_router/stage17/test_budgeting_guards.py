import yaml


def test_stage17_output_schema_allows_budget_config_invalid_status() -> None:
    from app.services.llm_chat.capability_router.ssot_loader import \
        get_output_schemas_path

    path = get_output_schemas_path()
    raw = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)

    schemas = doc.get("schemas") if isinstance(doc, dict) else {}
    partial = schemas.get("partial_result_v1") if isinstance(schemas, dict) else {}
    props = partial.get("properties") if isinstance(partial, dict) else {}
    status = props.get("status") if isinstance(props, dict) else {}
    enum = status.get("enum") if isinstance(status, dict) else []

    assert "budget_config_invalid" in list(enum)


def test_stage17_budget_guard_unenforceable_partial_result_shape_is_valid_against_enum_subset() -> None:
    from app.services.llm_chat.capability_router.ssot_loader import \
        load_output_schemas

    schemas = load_output_schemas().get("schemas")
    partial = schemas.get("partial_result_v1") if isinstance(schemas, dict) else {}
    props = partial.get("properties") if isinstance(partial, dict) else {}
    enum = props.get("status", {}).get("enum", [])

    payload = {
        "mode": "ACTION",
        "status": "budget_config_invalid",
        "detected_capability_id": "budget_guard_unenforceable",
        "what_ran": [],
        "missing_fields": [],
        "next_step": "contact_support",
    }

    assert payload["status"] in enum
    for key in ("mode", "status", "detected_capability_id", "what_ran", "missing_fields", "next_step"):
        assert key in payload


def test_stage17_budget_guard_unenforceable_emits_events_and_returns_partial(db_session, monkeypatch) -> None:
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    from app.schemas.llm_chat import ChatMessage, ChatRequest

    monkeypatch.setenv("CAP_ROUTER_MAX_TOOL_CALLS", "10")

    events: list[dict] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = (trace_id, kwargs)
        events.append({"event_type": event_type, "payload": payload})

    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)

    req = ChatRequest(messages=[ChatMessage(role="user", content="x")], client_id=1, pension_portfolio=None)

    res = tool_exec_mod.execute_with_guard(
        request=req,
        db=db_session,
        tool_name="GET_SYSTEM_NUMERIC_CONSTANTS",
        tool_call_id="tc_budget_1",
        tool_args={},
        streaming=False,
        policy_decision=None,
        intent_type=None,
        pension_portfolio=None,
        force_max_exemption=False,
        agent_reply=None,
        user_approved=True,
        request_id="r_budget_1",
    )

    assert isinstance(res, dict)
    assert res.get("status") == "budget_config_invalid"
    assert res.get("next_step") == "contact_support"

    event_types = [e.get("event_type") for e in events]
    assert "budget_guard_unenforceable" in event_types
    assert "partial_returned" in event_types

    unenf = [e for e in events if e.get("event_type") == "budget_guard_unenforceable"]
    assert unenf
    up = unenf[0].get("payload")
    assert isinstance(up, dict)
    assert set(up.keys()) == {"guard", "mode"}
    assert up.get("guard") == "max_tool_calls"
    assert up.get("mode") == "per_tool"

    partials = [e for e in events if e.get("event_type") == "partial_returned"]
    assert partials
    pp = partials[0].get("payload")
    assert isinstance(pp, dict)
    assert set(pp.keys()) in ({"status"}, {"status", "detected_capability_id"})
    assert pp.get("status") == "budget_config_invalid"
