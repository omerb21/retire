import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_find_optimal_scenario(*, args: dict, agent_tools: AgentToolsService) -> str:
    target_monthly_pension = args.get("target_monthly_pension")
    if target_monthly_pension is None:
        return "Error: Missing argument 'target_monthly_pension'"

    min_retirement_age = args.get("min_retirement_age")
    max_retirement_age = args.get("max_retirement_age")

    min_age_val = int(min_retirement_age) if min_retirement_age is not None else None
    max_age_val = int(max_retirement_age) if max_retirement_age is not None else None

    result = agent_tools.find_optimal_scenario_for_target(
        target_monthly_pension=float(target_monthly_pension),
        min_retirement_age=min_age_val,
        max_retirement_age=max_age_val,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
