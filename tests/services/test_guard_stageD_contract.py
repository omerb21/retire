from __future__ import annotations


def test_v2_returns_guardresult_shape() -> None:
    from app.services.llm_chat.guards.tool_execution_guard import (
        GuardOutcome,
        evaluate_tool_execution_guard_v2,
    )

    allowed = evaluate_tool_execution_guard_v2(
        tool_name="BUILD_TARGET_PENSION_PLAN",
        request_kind="build",
        has_pending_approval=False,
        user_intent=None,
    )
    assert allowed.outcome in {GuardOutcome.ALLOW, GuardOutcome.BLOCK, GuardOutcome.PENDING}

    if allowed.outcome == GuardOutcome.ALLOW:
        assert allowed.error_code is None
        assert allowed.approval_request_id is None

    if allowed.outcome == GuardOutcome.BLOCK:
        assert isinstance(allowed.error_code, str) and allowed.error_code
        assert allowed.approval_request_id is None

    if allowed.outcome == GuardOutcome.PENDING:
        assert allowed.error_code is None
        assert isinstance(allowed.approval_request_id, str) and allowed.approval_request_id


def test_v2_mapping_matches_legacy_entrypoint(monkeypatch) -> None:
    import app.services.llm_chat.guards.tool_execution_guard as mod

    def _allow(**kwargs) -> bool:
        return True

    def _block(**kwargs) -> bool:
        return False

    monkeypatch.setattr(mod, "can_execute_tool", _allow)
    r1 = mod.evaluate_tool_execution_guard_v2(
        tool_name="X",
        request_kind=None,
        has_pending_approval=False,
        user_intent=None,
    )
    assert r1.outcome == mod.GuardOutcome.ALLOW

    monkeypatch.setattr(mod, "can_execute_tool", _block)
    r2 = mod.evaluate_tool_execution_guard_v2(
        tool_name="X",
        request_kind=None,
        has_pending_approval=False,
        user_intent=None,
    )
    assert r2.outcome == mod.GuardOutcome.BLOCK
    assert r2.error_code == mod.DEFAULT_GUARD_BLOCK_CODE
    assert r2.approval_request_id is None
