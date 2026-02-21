from __future__ import annotations

from typing import Any, Callable

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.llm_chat import ChatMessage, ChatRequest


# NOTE: We intentionally do NOT include a GREETING_SHORTCUT parity flow here.
# compute_feature_flags disables greeting under PYTEST_CURRENT_TEST, and we must not
# change product behavior (or “leak env”) to the core just to make greeting testable.


def _capture_core_run(
    *,
    monkeypatch,
    run_fn: Callable[[], Any],
):
    import app.services.agent_execution.execute_agent_request as wrapper_mod

    core_event_types: list[str] = []
    core_decisions: list[Any] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        if isinstance(event_type, str) and event_type.startswith("core_"):
            core_event_types.append(event_type)

    orig_orchestrate = wrapper_mod.orchestrate

    def wrapped_orchestrate(*args, **kwargs):
        decision, trace_specs = orig_orchestrate(*args, **kwargs)
        core_decisions.append(decision)
        return decision, trace_specs

    monkeypatch.setattr(wrapper_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(wrapper_mod, "orchestrate", wrapped_orchestrate)

    run_fn()

    return {
        "core_event_types": core_event_types,
        "core_decisions": core_decisions,
        "first_core_decision": core_decisions[0] if core_decisions else None,
    }


def _post_non_stream(*, api: TestClient, client_id: int, user_text: str, executor_only: bool = False):
    payload = {
        "client_id": client_id,
        "executor_only": bool(executor_only),
        "messages": [{"role": "user", "content": user_text}],
        "pension_portfolio": [],
    }
    return api.post("/api/v1/llm/pension-chat", json=payload)


def _post_stream(*, api: TestClient, client_id: int, user_text: str, executor_only: bool = False):
    payload = {
        "client_id": client_id,
        "executor_only": bool(executor_only),
        "messages": [{"role": "user", "content": user_text}],
        "pension_portfolio": [],
    }
    return api.post("/api/v1/llm/pension-chat-stream", json=payload)


def _assert_wrapper_derived_parity(
    *,
    non_stream: dict,
    stream: dict,
    assert_plan_kind: bool,
    allowed_plan_kinds: set | None = None,
) -> None:
    from app.services.llm_chat.orchestration_core.canonicalize import canonicalize_tool_args

    d1 = non_stream["first_core_decision"]
    d2 = stream["first_core_decision"]

    assert d1 is not None
    assert d2 is not None

    assert getattr(d1, "decision_code", None) == getattr(d2, "decision_code", None)
    if assert_plan_kind:
        assert getattr(d1, "plan_kind", None) == getattr(d2, "plan_kind", None)
    elif allowed_plan_kinds is not None:
        assert getattr(d1, "plan_kind", None) in allowed_plan_kinds
        assert getattr(d2, "plan_kind", None) in allowed_plan_kinds

    if getattr(d1, "decision_code", None).value == "tool_call":
        assert getattr(d1, "tool_name", None) == getattr(d2, "tool_name", None)

        tool_name = str(getattr(d1, "tool_name", "") or "")
        args1 = getattr(d1, "tool_args", None) or {}
        args2 = getattr(d2, "tool_args", None) or {}
        assert canonicalize_tool_args(tool_name, args1, defaults=None) == canonicalize_tool_args(
            tool_name, args2, defaults=None
        )

    assert non_stream["core_event_types"] == stream["core_event_types"]


def test_parity_snapshot_stream_vs_nonstream(monkeypatch, client) -> None:
    api = TestClient(app)
    from app.services.llm_chat.orchestration_core.core_types import PlanKind

    non_stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_non_stream(api=api, client_id=int(client.id), user_text="GET_CLIENT_SNAPSHOT"),
    )
    stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_stream(api=api, client_id=int(client.id), user_text="GET_CLIENT_SNAPSHOT"),
    )

    _assert_wrapper_derived_parity(
        non_stream=non_stream,
        stream=stream,
        assert_plan_kind=True,
    )

    assert getattr(non_stream["first_core_decision"], "plan_kind", None) == PlanKind.SYSTEM_SNAPSHOT


def test_parity_termination_conceptual_stream_vs_nonstream(monkeypatch, client) -> None:
    api = TestClient(app)
    user_text = "בצע עזיבת עבודה בתאריך 2025-12-31 (בלי לבצע, הסבר עקרון בלבד)"
    from app.services.llm_chat.orchestration_core.core_types import PlanKind

    non_stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_non_stream(api=api, client_id=int(client.id), user_text=user_text),
    )
    stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_stream(api=api, client_id=int(client.id), user_text=user_text),
    )

    _assert_wrapper_derived_parity(
        non_stream=non_stream,
        stream=stream,
        assert_plan_kind=False,
        allowed_plan_kinds={PlanKind.QA_ONLY},
    )


def test_parity_monthly_pension_summary_stream_vs_nonstream(monkeypatch, client) -> None:
    api = TestClient(app)
    from app.services.llm_chat.orchestration_core.core_types import PlanKind

    non_stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_non_stream(api=api, client_id=int(client.id), user_text="monthly_pension"),
    )
    stream = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_stream(api=api, client_id=int(client.id), user_text="monthly_pension"),
    )

    _assert_wrapper_derived_parity(
        non_stream=non_stream,
        stream=stream,
        assert_plan_kind=False,
        allowed_plan_kinds={PlanKind.QA_ONLY},
    )


def test_nonstream_exec_only_tool_call_contract(monkeypatch, client) -> None:
    import app.services.agent_execution.execute_agent_request as wrapper_mod

    def fake_exec_only(*, request: ChatRequest, last_user_msg: str):
        _ = (request, last_user_msg)
        from app.schemas.llm_chat import ChatResponse

        return ChatResponse(reply="OK", computed_data=None)

    monkeypatch.setattr(wrapper_mod, "_run_execution_only_non_stream", fake_exec_only)

    api = TestClient(app)

    captured = _capture_core_run(
        monkeypatch=monkeypatch,
        run_fn=lambda: _post_non_stream(
            api=api,
            client_id=int(client.id),
            user_text="בדיקה",
            executor_only=True,
        ),
    )

    decision = captured["first_core_decision"]
    assert getattr(decision, "decision_code", None).value == "tool_call"
    assert getattr(decision, "tool_name", None) == "EXECUTION_ONLY"
    assert isinstance(getattr(decision, "tool_args", None), dict)
    assert (getattr(decision, "tool_args", None) or {}) == {}
