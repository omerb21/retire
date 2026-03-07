import json

import pytest

from app.schemas.llm_chat import ChatMessage
from app.services.llm_chat.orchestration_utils_parts import existing_income_offset
from tests.e2e.agent import test_behavior_golden_8 as golden_mod

_BEHAVIOR_06_CASE_ID = "BEHAVIOR_06_TARGET_NET_PERSIST_AND_NO_DOUBLE_OFFSET"


def _extract_payload(tool_output: str) -> dict:
    marker = "###TARGET_PENSION_PLAN_DATA###"
    end_marker = "###END_TARGET_PENSION_PLAN_DATA###"
    assert marker in tool_output
    assert end_marker in tool_output
    payload_text = tool_output.split(marker, 1)[1].split(end_marker, 1)[0].strip()
    return json.loads(payload_text)


def test_behavior_06_external_hook_is_narrow_and_uses_system_breakdown(
    client, db_session, monkeypatch
) -> None:
    original_compute = existing_income_offset.compute_effective_plan_target
    call_counter = {"count": 0}

    def _recording_compute(*args, **kwargs):
        call_counter["count"] += 1
        return original_compute(*args, **kwargs)

    monkeypatch.setattr(
        existing_income_offset,
        "compute_effective_plan_target",
        _recording_compute,
    )

    behavior_06_case = {"id": _BEHAVIOR_06_CASE_ID}
    control_case = {"id": "BEHAVIOR_05_PLANNING_REQUEST_MUST_NOT_EXECUTE_TERMINATION"}
    plan_args = {
        "target_monthly_pension": 30000,
        "target_is_net": True,
        "retirement_age": 76,
    }

    behavior_06_tool = golden_mod._FakeToolExecutor(behavior_06_case)
    tool_output = behavior_06_tool(
        "BUILD_TARGET_PENSION_PLAN",
        plan_args,
        client.id,
        db_session,
    )

    assert call_counter["count"] == 1
    assert "יעד כולל מבוקש (נטו): 30,000" in tool_output
    assert "קיזוז הכנסות נוספות (נטו): 8,880" in tool_output
    assert "יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): 21,120" in tool_output
    assert "12,239" not in tool_output
    assert "17,760" not in tool_output

    payload = _extract_payload(tool_output)
    assert payload["tool_name"] == "BUILD_TARGET_PENSION_PLAN"
    assert payload["args"]["target_is_net"] is True
    assert payload["args"]["retirement_age"] == 76
    assert payload["args"]["target_monthly_pension"] == pytest.approx(21119.6)
    assert payload["offsets"]["desired_net_total"] == pytest.approx(30000.0)
    assert payload["offsets"]["other_income_offset_net"] == pytest.approx(8880.4)
    assert payload["offsets"]["effective_plan_target"] == pytest.approx(21119.6)

    behavior_06_llm = golden_mod._FakeLLMService(behavior_06_case)
    llm_reply = behavior_06_llm.chat(
        [
            ChatMessage(role="user", content="בנה תכנית קצבת יעד 30000 נטו לגיל 76"),
            ChatMessage(
                role="system",
                content="🔧 **פלט כלי (בניית תכנית קצבה):**\n" + tool_output,
            ),
        ]
    )
    assert "יעד כולל מבוקש (נטו): 30,000" in llm_reply
    assert "קיזוז הכנסות נוספות (נטו): 8,880" in llm_reply
    assert "יעד קצבה לתכנית (נטו, אחרי קיזוז הכנסות נוספות): 21,120" in llm_reply
    assert "12,239" not in llm_reply

    control_tool = golden_mod._FakeToolExecutor(control_case)
    control_output = control_tool(
        "BUILD_TARGET_PENSION_PLAN",
        plan_args,
        client.id,
        db_session,
    )
    assert call_counter["count"] == 1
    assert "###TARGET_PENSION_PLAN_DATA###" not in control_output
    control_payload = json.loads(control_output)
    assert control_payload["target_monthly_pension"] == 30000
    assert control_payload["target_is_net"] is True
    assert control_payload["retirement_age"] == 76
