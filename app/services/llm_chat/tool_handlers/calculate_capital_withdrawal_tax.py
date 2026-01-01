import json

from datetime import datetime

from app.services.llm_agent_tools_service import AgentToolsService


def handle_calculate_capital_withdrawal_tax(*, args: dict, agent_tools: AgentToolsService) -> str:
    amount = args.get("withdrawal_amount_gross")
    year = args.get("withdrawal_year", datetime.now().year)

    if amount is None:
        return "Error: Missing argument 'withdrawal_amount_gross'"

    result = agent_tools.calculate_capital_withdrawal_tax(
        withdrawal_amount_gross=float(amount),
        withdrawal_year=int(year),
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
