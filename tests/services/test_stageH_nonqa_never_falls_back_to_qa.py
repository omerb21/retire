from __future__ import annotations

import asyncio


def test_stageH_nonqa_tool_blocked_never_calls_qa_fallback_non_stream(monkeypatch) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution import execute_agent_request as exec_mod
    from app.services.llm_chat.mcp.types import MCPOutcomeFinal

    def fake_chat(*args, **kwargs):
        raise AssertionError("QA fallback must not be called for non-QA TOOL_BLOCKED")

    monkeypatch.setattr(exec_mod.pension_llm_service, "chat", fake_chat)

    def fake_evaluate(self, *args, **kwargs):
        _ = (self, args, kwargs)
        return exec_mod.MCPDecision(
            execution_mode=exec_mod.MCPExecutionMode.TOOL_BLOCKED,
            reason_code="TEST_BLOCK",
            capability_id="nonqa_cap_v1",
            intent_tier="TEST",
            intent_type=None,
            outcome_final=MCPOutcomeFinal.TOOL_BLOCKED,
        )

    monkeypatch.setattr(exec_mod.MCPEngine, "evaluate", fake_evaluate)

    req = ChatRequest(messages=[ChatMessage(role="user", content="do action")], client_id=1)
    res = exec_mod.execute_agent_request(req, db=None)
    assert isinstance(getattr(res, "reply", None), str)
    assert "הבקשה נחסמה לפי מדיניות" in res.reply


def test_stageH_nonqa_pending_never_calls_qa_fallback_stream(monkeypatch) -> None:
    from app.schemas.llm_chat import ChatMessage, ChatRequest
    from app.services.agent_execution import execute_agent_request as exec_mod
    from app.services.llm_chat.mcp.types import MCPOutcomeFinal

    def fake_chat(*args, **kwargs):
        raise AssertionError("QA fallback must not be called for non-QA PENDING_APPROVAL")

    monkeypatch.setattr(exec_mod.pension_llm_service, "chat", fake_chat)

    def fake_evaluate(self, *args, **kwargs):
        _ = (self, args, kwargs)
        return exec_mod.MCPDecision(
            execution_mode=exec_mod.MCPExecutionMode.PENDING_APPROVAL,
            reason_code="TEST_PENDING",
            capability_id="nonqa_cap_v1",
            intent_tier="TEST",
            intent_type=None,
            outcome_final=MCPOutcomeFinal.PENDING_APPROVAL,
        )

    monkeypatch.setattr(exec_mod.MCPEngine, "evaluate", fake_evaluate)

    req = ChatRequest(messages=[ChatMessage(role="user", content="do action")], client_id=1)
    res = exec_mod.execute_agent_request_stream(req, db=None)

    async def _collect_body() -> str:
        chunks: list[str] = []
        async for chunk in res.body_iterator:
            if isinstance(chunk, (bytes, bytearray)):
                chunks.append(chunk.decode("utf-8", errors="ignore"))
            else:
                chunks.append(str(chunk))
        return "".join(chunks)

    body = asyncio.run(_collect_body())
    assert "נדרש אישור" in body
