from __future__ import annotations

import asyncio


def test_stageH_no_duplicate_mcp_decision_emit_non_stream(monkeypatch) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution import execute_agent_request as exec_mod
    from app.services.agent_eyes import event_collector
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    events: list[dict] = []

    def spy_emit_event(*, event_type: str, payload, client_id=None, endpoint=None) -> None:
        events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "client_id": client_id,
                "endpoint": endpoint,
            }
        )

    monkeypatch.setattr(event_collector, "emit_event", spy_emit_event)
    monkeypatch.setattr(exec_mod, "_eyes_emit", spy_emit_event)

    monkeypatch.setattr(
        exec_mod,
        "ensure_router_decision",
        lambda **kwargs: type("_D", (), {"capability_id": "default_qa_v1"})(),
    )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.RESPOND_ONLY,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=None,
                tool_args=None,
                final_text="ok",
                requires_user_approval=False,
                debug_meta=None,
            ),
            [],
        )

    monkeypatch.setattr(exec_mod, "orchestrate", fake_orchestrate)

    def passthrough_max_iter_guard(
        *, iter_idx, max_iterations, trace_id, final_text, decision, trace_specs
    ):
        _ = (iter_idx, max_iterations, trace_id, final_text)
        return decision, trace_specs, False

    monkeypatch.setattr(exec_mod, "maybe_apply_max_iterations_guard", passthrough_max_iter_guard)
    monkeypatch.setattr(exec_mod.pension_llm_service, "chat", lambda *a, **k: "ok")

    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")], client_id=1)
    _ = exec_mod.execute_agent_request(req, db=None)

    mcp_events = [e for e in events if e.get("event_type") == "mcp_decision"]
    assert len(mcp_events) == 1


def test_stageH_no_duplicate_mcp_decision_emit_stream(monkeypatch) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution import execute_agent_request as exec_mod
    from app.services.agent_eyes import event_collector
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    events: list[dict] = []

    def spy_emit_event(*, event_type: str, payload, client_id=None, endpoint=None) -> None:
        events.append(
            {
                "event_type": event_type,
                "payload": payload,
                "client_id": client_id,
                "endpoint": endpoint,
            }
        )

    monkeypatch.setattr(event_collector, "emit_event", spy_emit_event)
    monkeypatch.setattr(exec_mod, "_eyes_emit", spy_emit_event)

    monkeypatch.setattr(
        exec_mod,
        "ensure_router_decision",
        lambda **kwargs: type("_D", (), {"capability_id": "default_qa_v1"})(),
    )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.RESPOND_ONLY,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=None,
                tool_args=None,
                final_text="ok",
                requires_user_approval=False,
                debug_meta=None,
            ),
            [],
        )

    monkeypatch.setattr(exec_mod, "orchestrate", fake_orchestrate)

    def passthrough_max_iter_guard(
        *, iter_idx, max_iterations, trace_id, final_text, decision, trace_specs
    ):
        _ = (iter_idx, max_iterations, trace_id, final_text)
        return decision, trace_specs, False

    monkeypatch.setattr(exec_mod, "maybe_apply_max_iterations_guard", passthrough_max_iter_guard)
    monkeypatch.setattr(exec_mod.pension_llm_service, "chat", lambda *a, **k: "ok")

    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")], client_id=1)
    res = exec_mod.execute_agent_request_stream(req, db=None)

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in res.body_iterator:
            if isinstance(chunk, (bytes, bytearray)):
                chunks.append(chunk.decode("utf-8", errors="ignore"))
            else:
                chunks.append(str(chunk))
        return "".join(chunks)

    _ = asyncio.run(_collect_body())

    mcp_events = [e for e in events if e.get("event_type") == "mcp_decision"]
    assert len(mcp_events) == 1
