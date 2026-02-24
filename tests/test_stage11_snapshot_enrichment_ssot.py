from app.services.llm_chat.orchestration_core.core_types import ToolResultEnvelope
from app.services.llm_chat.orchestration_core.snapshot_enrichment import (
    enrich_state_snapshot,
)


def test_enrich_state_snapshot_tax_autochain_gross_monthly_pension_written_for_net_build_target_plan():
    state = {}
    user_text = "אני רוצה יעד נטו"
    env = ToolResultEnvelope(
        tool_name="BUILD_TARGET_PENSION_PLAN",
        tool_args={},
        tool_result='{"accumulated_pension": 12345}',
        status="ok",
        error_message=None,
        trace_id=None,
        tool_call_id=None,
    )

    out = enrich_state_snapshot(state, user_text=user_text, last_tool_result=env)

    assert isinstance(out, dict)
    assert out.get("tax_autochain_gross_monthly_pension") == 12345.0


def test_enrich_state_snapshot_facts_are_merged():
    out = enrich_state_snapshot(
        {},
        user_text="",
        last_tool_result=None,
        facts={"forced_document_reply_stop": True},
    )
    assert isinstance(out, dict)
    assert out.get("forced_document_reply_stop") is True
