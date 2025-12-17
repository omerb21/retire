import json

from app.services.llm_chat.state_tools import get_tools_definitions_json


def _get_tool(tools: list[dict], name: str) -> dict:
    for tool in tools:
        if tool.get("name") == name:
            return tool
    raise AssertionError(f"Tool not found in schema: {name}")


def test_submit_tax_commutation_schema_does_not_require_client_id() -> None:
    tools = json.loads(get_tools_definitions_json())
    tool = _get_tool(tools, "SUBMIT_TAX_COMMUTATION")
    required = tool.get("parameters", {}).get("required", [])
    description = tool.get("description") or ""

    assert "client_id" not in required
    assert "commutation_type" in required
    assert "tax_projection_id" in required
    assert "final_net_amount" in required
    assert "confirmed" in required

    # Guard against future ambiguity regressions
    assert "לא עזיבת עבודה" in description
    assert "client_id" in description
    assert "אופציונלי" in description


def test_process_termination_description_is_termination_scoped() -> None:
    tools = json.loads(get_tools_definitions_json())
    tool = _get_tool(tools, "PROCESS_TERMINATION")
    description = tool.get("description") or ""
    required = tool.get("parameters", {}).get("required", [])

    assert "עזיבת עבודה" in description
    assert "פיצויים" in description
    assert "termination_date" in required
    assert "severance_amount" in required
    assert "exempt_amount" in required
    assert "taxable_amount" in required
    assert "exempt_choice" in required
    assert "taxable_choice" in required
    assert "confirmed" in required


def test_llm_chat_package_exports_are_available() -> None:
    from app.services.llm_chat import get_tools_definitions_json as pkg_get_tools_definitions_json

    tools = json.loads(pkg_get_tools_definitions_json())
    _get_tool(tools, "PROCESS_TERMINATION")
    _get_tool(tools, "SUBMIT_TAX_COMMUTATION")


def test_global_system_prompt_contains_tool_distinction_rules() -> None:
    from app.services.llm_chat.prompts import get_global_system_prompt_base

    prompt = get_global_system_prompt_base()

    assert "PROCESS_TERMINATION" in prompt
    assert "SUBMIT_TAX_COMMUTATION" in prompt
    assert "כלל חובה (D9.1" in prompt
    assert "כלל בחירה" in prompt
