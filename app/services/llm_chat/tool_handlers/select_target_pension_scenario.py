import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_select_target_pension_scenario(
    *, args: dict, agent_tools: AgentToolsService
) -> str:
    target_monthly_pension = args.get("target_monthly_pension")
    if target_monthly_pension is None:
        return "Error: Missing argument 'target_monthly_pension'"

    retirement_age = args.get("retirement_age")
    retirement_age_val = int(retirement_age) if retirement_age is not None else None

    result = agent_tools.select_optimal_scenario_for_target_pension(
        target_monthly_pension=float(target_monthly_pension),
        retirement_age=retirement_age_val,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
