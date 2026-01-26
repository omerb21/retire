import json

from app.services.llm_chat.tool_handlers.build_target_pension_plan import handle_build_target_pension_plan


class _FakeAgentTools:
    def __init__(self, result: dict):
        self._result = result

    def build_target_pension_plan(self, target_monthly_pension, retirement_age=None, target_is_net=True):
        return self._result


def test_build_target_pension_plan_handler_defaults_to_net_mode_when_missing_arg() -> None:
    tool_res = {
        "success": True,
        "result": {
            "target_monthly_pension": 28000,
            "target_is_net": True,
            "target_achieved": False,
            "accumulated_pension": 30000,
            "estimated_monthly_tax": 6000,
            "estimated_monthly_net": 24000,
            "required_gross_for_target": 35000,
            "remaining_capital": 100000,
        },
        "explanation": "demo",
    }
    out = handle_build_target_pension_plan(args={"target_monthly_pension": 28000}, agent_tools=_FakeAgentTools(tool_res))
    assert "יעד קצבה חודשי (נטו)" in out
    assert "ברוטו שנדרש" in out
    assert "קצבה נטו משוערת" in out


def test_build_target_pension_plan_handler_respects_gross_mode() -> None:
    tool_res = {
        "success": True,
        "result": {
            "target_monthly_pension": 28000,
            "target_is_net": False,
            "target_achieved": True,
            "accumulated_pension": 28000,
            "remaining_capital": 0,
        },
        "explanation": "demo",
    }
    out = handle_build_target_pension_plan(
        args={"target_monthly_pension": 28000, "target_is_net": False},
        agent_tools=_FakeAgentTools(tool_res),
    )
    assert "יעד קצבה חודשי (ברוטו)" in out
    assert "קצבה ברוטו שהושגה" in out
    assert "קצבה נטו משוערת" not in out


def test_build_target_pension_plan_handler_emits_target_plan_payload_block() -> None:
    tool_res = {
        "success": True,
        "result": {
            "target_monthly_pension": 28000,
            "target_is_net": True,
            "target_achieved": True,
            "accumulated_pension": 42000,
            "estimated_monthly_tax": 14000,
            "estimated_monthly_net": 28000,
            "required_gross_for_target": 42000,
            "remaining_capital": 123,
        },
        "explanation": "demo",
    }
    out = handle_build_target_pension_plan(args={"target_monthly_pension": 28000}, agent_tools=_FakeAgentTools(tool_res))
    assert "###TARGET_PENSION_PLAN_DATA###" in out
    payload_raw = out.split("###TARGET_PENSION_PLAN_DATA###", 1)[1].split("###END_TARGET_PENSION_PLAN_DATA###", 1)[0]
    payload = json.loads(payload_raw)
    assert payload["tool_name"] == "BUILD_TARGET_PENSION_PLAN"
    assert payload["result"]["target_is_net"] is True


def test_build_target_pension_plan_handler_mentions_retirement_age_when_provided() -> None:
    tool_res = {
        "success": True,
        "result": {
            "target_monthly_pension": 28000,
            "target_is_net": True,
            "target_achieved": True,
            "accumulated_pension": 28000,
            "remaining_capital": 0,
        },
        "explanation": "demo",
    }
    out = handle_build_target_pension_plan(
        args={"target_monthly_pension": 28000, "retirement_age": 75},
        agent_tools=_FakeAgentTools(tool_res),
    )
    assert "גיל פרישה בתכנון" in out
    assert "75" in out
