from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def test_guard_metadata_is_copied_without_changing_execution_mode(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    decision = MCPEngine().evaluate(
        intent_tier="NO_TOOLS",
        intent_type="QA",
        router_decision=SimpleNamespace(capability_id="default_qa_v1", tool_chain=[]),
        guard_result={
            "tools_enabled": True,
            "outcome": "ALLOW",
            "error_code": None,
            "approval_request_id": None,
        },
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.execution_mode == MCPExecutionMode.NO_TOOLS
    assert decision.guard_present is True
    assert decision.guard_outcome == "ALLOW"
    assert decision.guard_error_code is None
    assert decision.guard_approval_request_id is None
