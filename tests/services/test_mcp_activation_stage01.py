def _build_req(*, text: str, client_id: int | None = 1):
    from app.schemas.llm_chat import ChatMessage, ChatRequest

    return ChatRequest(
        messages=[ChatMessage(role="user", content=text)], client_id=client_id
    )


def test_stream_no_tools_never_executes_tool(monkeypatch, db_session) -> None:
    from app.services.agent_execution import execute_agent_request as core_mod
    from app.services.llm_chat.explicit_tool_shortcuts import CLIENT_SNAPSHOT_TOOL_NAME
    from app.services.llm_chat.mcp.types import MCPDecision, MCPExecutionMode
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    calls: dict[str, int] = {"tool_exec": 0, "mcp_eval": 0}

    def fake_execute_with_guard(*args, **kwargs):
        calls["tool_exec"] += 1
        raise AssertionError("tool executor should not be called")

    def fake_mcp_eval(self, **kwargs):
        calls["mcp_eval"] += 1
        return MCPDecision(
            execution_mode=MCPExecutionMode.NO_TOOLS,
            reason_code="no_tools",
            capability_id="default_qa_v1",
            intent_tier="T",
            intent_type=None,
        )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.TOOL_CALL,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
                tool_args={},
                final_text=None,
                requires_user_approval=False,
                debug_meta=None,
            ),
            [],
        )

    monkeypatch.setattr(core_mod, "execute_with_guard", fake_execute_with_guard)
    monkeypatch.setattr(core_mod.MCPEngine, "evaluate", fake_mcp_eval)
    monkeypatch.setattr(core_mod, "orchestrate", fake_orchestrate)
    monkeypatch.setattr(core_mod.pension_llm_service, "chat", lambda *a, **k: "ok")

    resp = core_mod.execute_agent_request_stream(
        _build_req(text="x", client_id=1), db_session
    )

    assert calls["mcp_eval"] == 1
    assert calls["tool_exec"] == 0
    assert resp is not None


def test_nonqa_capability_cannot_legacy_fallback(monkeypatch, db_session) -> None:
    from app.services.agent_execution import execute_agent_request as core_mod
    from app.services.llm_chat.mcp.types import MCPDecision, MCPExecutionMode
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    calls: dict[str, int] = {"tool_exec": 0, "legacy": 0, "mcp_eval": 0}

    def fake_execute_with_guard(*args, **kwargs):
        calls["tool_exec"] += 1
        raise AssertionError("tool executor should not be called")

    def fake_mcp_eval(self, **kwargs):
        calls["mcp_eval"] += 1
        from app.services.llm_chat.mcp.types import MCPOutcomeFinal

        return MCPDecision(
            execution_mode=MCPExecutionMode.TOOL_ALLOWED,
            reason_code="ok",
            capability_id="build_target_plan_v1",
            intent_tier="T",
            intent_type=None,
            outcome_final=MCPOutcomeFinal.TOOL_BLOCKED,
        )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.BLOCKED,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=None,
                tool_args=None,
                final_text=None,
                requires_user_approval=False,
                debug_meta=None,
            ),
            [],
        )

    import app.services.llm_chat.chat_orchestration as chat_orch

    def fake_run_pension_chat(*args, **kwargs):
        calls["legacy"] += 1
        return core_mod.ChatResponse(reply="legacy", computed_data=None)

    monkeypatch.setattr(core_mod, "execute_with_guard", fake_execute_with_guard)
    monkeypatch.setattr(core_mod.MCPEngine, "evaluate", fake_mcp_eval)
    monkeypatch.setattr(core_mod, "orchestrate", fake_orchestrate)
    monkeypatch.setattr(chat_orch, "run_pension_chat", fake_run_pension_chat)

    res = core_mod.execute_agent_request(_build_req(text="x", client_id=1), db_session)

    assert calls["mcp_eval"] == 1
    assert calls["legacy"] == 0
    assert calls["tool_exec"] == 0
    assert isinstance(getattr(res, "reply", None), str)
    assert "הבקשה נחסמה לפי מדיניות" in res.reply
    assert "reason_code=ok" in res.reply


def test_stream_tool_call_blocked_by_mcp(monkeypatch, db_session) -> None:
    from app.services.agent_execution import execute_agent_request as core_mod
    from app.services.llm_chat.explicit_tool_shortcuts import CLIENT_SNAPSHOT_TOOL_NAME
    from app.services.llm_chat.mcp.types import MCPDecision, MCPExecutionMode
    from app.services.llm_chat.orchestration_core.core_types import (
        DecisionCode,
        OrchestrationDecision,
        PlanKind,
    )

    calls: dict[str, int] = {"tool_exec": 0, "mcp_eval": 0}

    def fake_execute_with_guard(*args, **kwargs):
        calls["tool_exec"] += 1
        raise AssertionError("tool executor should not be called")

    def fake_mcp_eval(self, **kwargs):
        calls["mcp_eval"] += 1
        return MCPDecision(
            execution_mode=MCPExecutionMode.PENDING_APPROVAL,
            reason_code="pending",
            capability_id="default_qa_v1",
            intent_tier="T",
            intent_type=None,
        )

    def fake_orchestrate(_inp, _deps):
        return (
            OrchestrationDecision(
                decision_code=DecisionCode.TOOL_CALL,
                plan_kind=PlanKind.QA_ONLY,
                tool_name=CLIENT_SNAPSHOT_TOOL_NAME,
                tool_args={},
                final_text=None,
                requires_user_approval=False,
                debug_meta=None,
            ),
            [],
        )

    monkeypatch.setattr(core_mod, "execute_with_guard", fake_execute_with_guard)
    monkeypatch.setattr(core_mod.MCPEngine, "evaluate", fake_mcp_eval)
    monkeypatch.setattr(core_mod, "orchestrate", fake_orchestrate)

    resp = core_mod.execute_agent_request_stream(
        _build_req(text="x", client_id=1), db_session
    )

    assert calls["mcp_eval"] == 1
    assert calls["tool_exec"] == 0
    assert resp is not None
