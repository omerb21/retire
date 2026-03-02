from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def test_stageF_capability_gap_closure_forces_outcome_tool_blocked(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode, MCPOutcomeFinal

    decision = MCPEngine().evaluate(
        intent_tier="ANALYSIS",
        intent_type="QA",
        router_decision=SimpleNamespace(
            capability_id="some_non_default_capability",
            tool_chain=[],
        ),
        guard_result={
            "tools_enabled": True,
            "outcome": "ALLOW",
            "error_code": None,
            "approval_request_id": None,
        },
        had_new_core_entered=False,
        legacy_requested=False,
    )

    # Must not change execution_mode.
    assert decision.execution_mode == MCPExecutionMode.NO_TOOLS

    # But the canonical outcome must be blocked due to capability gap closure.
    assert decision.outcome_final == MCPOutcomeFinal.TOOL_BLOCKED
    assert decision.policy_violation is True
    assert decision.policy_violation_reason == "BEHAVIOR_NOT_ACTIVATED"


def test_stageF_capability_gap_closure_does_not_apply_to_default_qa(
    monkeypatch,
) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode, MCPOutcomeFinal

    decision = MCPEngine().evaluate(
        intent_tier="ANALYSIS",
        intent_type="QA",
        router_decision=SimpleNamespace(
            capability_id="default_qa_v1",
            tool_chain=[],
        ),
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
    assert decision.outcome_final == MCPOutcomeFinal.NO_TOOLS
    assert decision.policy_violation is False
    assert decision.policy_violation_reason is None
