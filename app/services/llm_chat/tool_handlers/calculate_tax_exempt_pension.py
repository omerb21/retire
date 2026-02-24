import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_calculate_tax_exempt_pension(
    *, args: dict, agent_tools: AgentToolsService
) -> str:
    grant_amount = args.get("current_tax_exempt_grant_amount")
    if grant_amount is None:
        return "Error: Missing argument 'current_tax_exempt_grant_amount'"

    result = agent_tools.calculate_tax_exempt_pension(
        current_tax_exempt_grant_amount=float(grant_amount)
    )
    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
