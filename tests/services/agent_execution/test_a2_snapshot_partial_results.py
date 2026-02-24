import pytest


def test_a2_snapshot_with_client_id_returns_computed_data(
    db_session, client, monkeypatch
) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    trace_id = "trace_a2_snapshot_with_client_id"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="GET_CLIENT_SNAPSHOT")],
        client_id=int(client.id),
        pension_portfolio=None,
    )
    res = execute_agent_request(req, db_session)

    computed_data = getattr(res, "computed_data", None)
    assert isinstance(computed_data, dict)
    assert computed_data.get("tool_name") == "GET_CLIENT_SNAPSHOT"
    assert computed_data.get("success") is True
    assert isinstance(computed_data.get("breakdown"), dict)


def test_a2_snapshot_without_client_id_returns_partial_missing_data(
    db_session, monkeypatch
) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    trace_id = "trace_a2_snapshot_missing_client_id"
    set_current_trace_id(trace_id)
    try:
        db_session.info["trace_id"] = trace_id
    except Exception:
        pass

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="GET_CLIENT_SNAPSHOT")],
        client_id=None,
        pension_portfolio=None,
    )
    res = execute_agent_request(req, db_session)

    computed_data = getattr(res, "computed_data", None)
    assert isinstance(computed_data, dict)
    assert computed_data.get("status") == "missing_data"
    assert computed_data.get("missing_fields") == ["client_id"]


def test_a2_capability_map_source_is_stage16_fixture(monkeypatch) -> None:
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    cap_map = load_capability_map()
    assert isinstance(cap_map, dict)
    assert cap_map.get("capability_map_version") == "16.0.0"
    caps = cap_map.get("capabilities")
    assert isinstance(caps, list)
    assert len(caps) >= 2
