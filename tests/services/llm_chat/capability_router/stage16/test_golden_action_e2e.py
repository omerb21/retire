import json
from typing import Any

import pytest
import yaml


def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded if isinstance(loaded, dict) else {}


def _capture_all_trace_events(monkeypatch):
    import app.services.agent_execution.execute_agent_request as entry_mod
    import app.services.agent_execution.tool_executor as tool_exec_mod
    import app.services.agent_trace_logger as trace_logger_mod
    import app.services.llm_chat.tool_execution as tool_execution_mod

    events: list[dict[str, Any]] = []

    def fake_log_trace_event(*, trace_id=None, event_type: str, payload=None, **kwargs):
        _ = kwargs
        events.append(
            {"trace_id": trace_id, "event_type": event_type, "payload": payload}
        )

    monkeypatch.setattr(entry_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(trace_logger_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_execution_mod, "_log_agent_trace", fake_log_trace_event)

    return events


def _assert_no_duplicate_tool_calls(
    events: list[dict[str, Any]], trace_id: str
) -> None:
    tool_calls = []
    for e in events:
        if e.get("trace_id") != trace_id:
            continue
        if e.get("event_type") != "tool_call":
            continue
        payload = e.get("payload")
        if not isinstance(payload, dict):
            continue
        if not isinstance(payload.get("args"), dict):
            continue
        tool_calls.append(payload)

    seen: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for p in tool_calls:
        tool_name = str(p.get("tool_name") or "")
        args = p.get("args") if isinstance(p.get("args"), dict) else {}
        key = (tool_name, json.dumps(args, sort_keys=True, ensure_ascii=False))
        seen.setdefault(key, []).append(p)

    for (tool_name, _args_str), payloads in seen.items():
        if len(payloads) <= 1:
            continue
        for p in payloads:
            if not (
                ("retry_reason" in p)
                and ("attempt_index" in p)
                and ("retry_policy" in p)
            ):
                raise AssertionError(
                    f"Duplicate tool call detected without retry metadata: tool={tool_name}"
                )


def _find_router_selected_payload(
    events: list[dict[str, Any]], trace_id: str
) -> dict[str, Any]:
    for e in events:
        if e.get("trace_id") != trace_id:
            continue
        if e.get("event_type") != "router_selected":
            continue
        payload = e.get("payload")
        if isinstance(payload, dict):
            return payload
    raise AssertionError("router_selected event not found")


def test_stage16_golden_action_e2e(db_session, client, monkeypatch) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution.execute_agent_request import execute_agent_request
    from app.services.agent_execution.tool_executor import execute_with_guard
    from app.services.llm_chat.capability_router.ssot_loader import load_capability_map
    from app.services.llm_chat.orchestration_core.core_types import (
        OrchestrationDeps,
        OrchestrationInput,
    )
    from app.services.llm_chat.orchestration_core.orchestrate import orchestrate
    from app.utils.trace_context import set_current_trace_id

    monkeypatch.setenv(
        "CAPABILITY_MAP_PATH", "tests/fixtures/stage16/capability_map_stage16.yaml"
    )
    load_capability_map.cache_clear()

    fixture = _load_yaml("tests/fixtures/stage16/golden_action_cases.yaml")
    cases = fixture.get("cases") if isinstance(fixture.get("cases"), list) else []
    assert cases

    for c in cases:
        case_id = str(c.get("case_id") or "")
        user_text = str(c.get("user_text") or "")
        expected = c.get("expected") if isinstance(c.get("expected"), dict) else {}
        expected_capability_id = expected.get("capability_id")
        expected_tool_chain = expected.get("tool_chain")
        expected_schema_id = expected.get("output_schema_id")
        expected_cd_keys = (
            expected.get("computed_data_keys")
            if isinstance(expected.get("computed_data_keys"), list)
            else []
        )

        for run_idx in range(5):
            trace_id = f"trace_stage16_action_{case_id}_{run_idx}"
            set_current_trace_id(trace_id)
            try:
                db_session.info["trace_id"] = trace_id
            except Exception:
                pass

            events = _capture_all_trace_events(monkeypatch)

            if isinstance(c.get("tool_execution"), dict):
                deps = OrchestrationDeps(
                    llm_generate=lambda _messages, _client_id=None: "",
                    tool_defaults=lambda _tool_name: {},
                )
                oin = OrchestrationInput(
                    user_text=user_text,
                    client_id=int(client.id),
                    session_id=None,
                    conversation_id=None,
                    trace_id=trace_id,
                    feature_flags={},
                    request_meta=None,
                    state_snapshot={"tools_enabled": True},
                    last_tool_result=None,
                )
                _d, specs = orchestrate(oin, deps)
                for s in specs:
                    events.append(
                        {
                            "trace_id": s.trace_id,
                            "event_type": s.event_type,
                            "payload": s.payload,
                        }
                    )

                te = c.get("tool_execution")
                tool_name = str(te.get("tool_name") or "")
                tool_args = (
                    te.get("tool_args") if isinstance(te.get("tool_args"), dict) else {}
                )

                req = ChatRequest(
                    messages=[ChatMessage(role="user", content=user_text)],
                    client_id=int(client.id),
                    pension_portfolio=None,
                )

                _ = execute_with_guard(
                    request=req,
                    db=db_session,
                    tool_name=tool_name,
                    tool_call_id="tc_stage16",
                    tool_args=tool_args,
                    streaming=False,
                    policy_decision=None,
                    intent_type=None,
                    pension_portfolio=None,
                    force_max_exemption=False,
                    agent_reply=None,
                    user_approved=True,
                    request_id=None,
                )

                computed_data = None
            else:
                req = ChatRequest(
                    messages=[ChatMessage(role="user", content=user_text)],
                    client_id=int(client.id),
                    pension_portfolio=None,
                )
                res = execute_agent_request(req, db_session)
                computed_data = getattr(res, "computed_data", None)

            router_payload = _find_router_selected_payload(events, trace_id)
            assert router_payload.get("capability_id") == expected_capability_id
            assert router_payload.get("tool_chain") == expected_tool_chain
            assert router_payload.get("output_schema_id") == expected_schema_id

            cd_keys = (
                set(computed_data.keys()) if isinstance(computed_data, dict) else set()
            )
            assert cd_keys == set(str(x) for x in expected_cd_keys)

            _assert_no_duplicate_tool_calls(events, trace_id)
