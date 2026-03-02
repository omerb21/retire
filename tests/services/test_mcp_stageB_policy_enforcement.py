from __future__ import annotations


def _reset_ssot_loader(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITY_MAP_PATH", raising=False)
    monkeypatch.delenv("CAPABILITY_ROUTER_CANARY_MODE", raising=False)

    from app.services.llm_chat.capability_router import ssot_loader

    ssot_loader.load_capability_map.cache_clear()
    ssot_loader.load_output_schemas.cache_clear()
    ssot_loader.load_ssot_v1.cache_clear()


def test_mapping_missing_sets_violation_when_flag_on(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import POLICY_MAPPING_MISSING
    from app.services.llm_chat.mcp.engine import MCPEngine

    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_B1", "1")
    monkeypatch.setattr(
        MCPEngine,
        "_resolve_side_effect_class",
        staticmethod(lambda capability_id: "READ_ONLY"),
    )
    monkeypatch.setattr(
        MCPEngine,
        "_apply_policy_matrix",
        lambda self, intent_tier, intent_type, side_effect_class: None,
    )

    decision = MCPEngine().evaluate(
        intent_tier="REPORT",
        intent_type="PLAN",
        router_decision=SimpleNamespace(capability_id="default_qa_v1", tool_chain=[]),
        guard_result={"tools_enabled": True},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.policy_allowed_execution_modes is None
    assert decision.policy_violation is True
    assert decision.policy_violation_reason == POLICY_MAPPING_MISSING


def test_flag_off_preserves_overlay_behavior(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import POLICY_MAPPING_MISSING
    from app.services.llm_chat.mcp.engine import MCPEngine

    monkeypatch.delenv("MCP_POLICY_ENFORCEMENT_B1", raising=False)
    monkeypatch.setattr(
        MCPEngine,
        "_resolve_side_effect_class",
        staticmethod(lambda capability_id: "READ_ONLY"),
    )
    monkeypatch.setattr(
        MCPEngine,
        "_apply_policy_matrix",
        lambda self, intent_tier, intent_type, side_effect_class: None,
    )

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


def test_keeps_mode_when_allowed(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_B1", "1")
    monkeypatch.setattr(
        MCPEngine,
        "_resolve_side_effect_class",
        staticmethod(lambda capability_id: "READ_ONLY"),
    )
    monkeypatch.setattr(
        MCPEngine,
        "_apply_policy_matrix",
        lambda self, intent_tier, intent_type, side_effect_class: ["TOOL_ALLOWED"],
    )

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
    assert decision.policy_allowed_execution_modes == ["TOOL_ALLOWED"]
    assert decision.policy_violation is False


def test_downgrades_when_not_allowed(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.decision import POLICY_VIOLATION
    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_B1", "1")
    monkeypatch.setattr(
        MCPEngine,
        "_resolve_side_effect_class",
        staticmethod(lambda capability_id: "READ_ONLY"),
    )
    monkeypatch.setattr(
        MCPEngine,
        "_apply_policy_matrix",
        lambda self, intent_tier, intent_type, side_effect_class: [
            "NO_TOOLS",
            "TOOL_BLOCKED",
        ],
    )

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

    assert decision.execution_mode == MCPExecutionMode.NO_TOOLS
    assert decision.policy_allowed_execution_modes == ["NO_TOOLS", "TOOL_BLOCKED"]
    assert decision.policy_violation is True
    assert decision.policy_violation_reason == POLICY_VIOLATION


def test_never_increases_permissions(monkeypatch) -> None:
    _reset_ssot_loader(monkeypatch)

    from types import SimpleNamespace

    from app.services.llm_chat.mcp.engine import MCPEngine
    from app.services.llm_chat.mcp.types import MCPExecutionMode

    monkeypatch.setenv("MCP_POLICY_ENFORCEMENT_B1", "1")
    monkeypatch.setattr(
        MCPEngine,
        "_resolve_side_effect_class",
        staticmethod(lambda capability_id: "READ_ONLY"),
    )
    monkeypatch.setattr(
        MCPEngine,
        "_apply_policy_matrix",
        lambda self, intent_tier, intent_type, side_effect_class: ["TOOL_ALLOWED"],
    )

    decision = MCPEngine().evaluate(
        intent_tier="NO_TOOLS",
        intent_type="QA",
        router_decision=SimpleNamespace(
            capability_id="default_qa_v1", tool_chain=["X"]
        ),
        guard_result={"tools_enabled": False},
        had_new_core_entered=False,
        legacy_requested=False,
    )

    assert decision.execution_mode == MCPExecutionMode.TOOL_BLOCKED
