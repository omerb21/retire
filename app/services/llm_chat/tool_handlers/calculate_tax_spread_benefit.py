import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_calculate_tax_spread_benefit(*, args: dict, agent_tools: AgentToolsService) -> str:
    gross_amount = args.get("gross_amount")
    spread_years = args.get("spread_years")

    if gross_amount is None:
        return "Error: Missing argument 'gross_amount'"
    if spread_years is None:
        return "Error: Missing argument 'spread_years'"

    result = agent_tools.calculate_tax_spread_benefit(
        gross_amount=float(gross_amount),
        spread_years=int(spread_years),
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
