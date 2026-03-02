from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def test_policy_validation_sets_allowed_modes(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    decision = MCPEngine().evaluate(
        intent_tier="NO_TOOLS",
        intent_type="QA",
        router_decision=SimpleNamespace(capability_id="default_qa_v1", tool_chain=[]),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.policy_matrix_present is True
    assert decision.execution_mode == MCPExecutionMode.NO_TOOLS
    assert isinstance(decision.policy_allowed_execution_modes, list)
    assert decision.policy_allowed_execution_modes


def test_policy_violation_flag_only_no_behavior_change(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import POLICY_VIOLATION
    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    decision = MCPEngine().evaluate(
        intent_tier="NO_TOOLS",
        intent_type="QA",
        router_decision=SimpleNamespace(
            capability_id="default_qa_v1", tool_chain=["X"]
        ),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.execution_mode == MCPExecutionMode.TOOL_ALLOWED
    assert decision.policy_allowed_execution_modes == ["NO_TOOLS"]
    assert decision.policy_violation is True
    assert decision.policy_violation_reason == POLICY_VIOLATION


def test_mapping_missing_is_observability_only(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import POLICY_MAPPING_MISSING
    from app.services.llm_chat.mcp.engine import MCPEngine

    decision = MCPEngine().evaluate(
        intent_tier="REPORT",
        intent_type="PLAN",
        router_decision=SimpleNamespace(capability_id="default_qa_v1", tool_chain=[]),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.policy_allowed_execution_modes is None
    assert decision.policy_violation is False
    assert decision.policy_violation_reason == POLICY_MAPPING_MISSING


def test_side_effect_missing_is_observability_only(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import SIDE_EFFECT_CLASS_MISSING
    from app.services.llm_chat.mcp.engine import MCPEngine

    # SSOT validation forbids missing side_effect_class, so we simulate the runtime
    # case via an unknown capability_id.
    decision = MCPEngine().evaluate(
        intent_tier="NO_TOOLS",
        intent_type="QA",
        router_decision=SimpleNamespace(
            capability_id="capability_missing_v1", tool_chain=[]
        ),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.policy_allowed_execution_modes is None
    assert decision.policy_violation is False
    assert decision.policy_violation_reason == SIDE_EFFECT_CLASS_MISSING
