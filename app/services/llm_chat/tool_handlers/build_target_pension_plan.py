from app.services.llm_agent_tools_service import AgentToolsService


def handle_build_target_pension_plan(*, args: dict, agent_tools: AgentToolsService) -> str:
    target = args.get("target_monthly_pension")
    if not target:
        return "Error: Missing argument 'target_monthly_pension'"

    result = agent_tools.build_target_pension_plan(target_monthly_pension=float(target))
    if not result.get("success"):
        return f"Tool Error: {result.get('error', 'Unknown error')}"

    plan_res = result.get("result", {})
    summary = (
        "Calculation Complete:\n"
        f"- Target: {plan_res.get('target_monthly_pension'):,.0f}\n"
        f"- Achieved: {plan_res.get('accumulated_pension'):,.0f}\n"
        f"- Remaining Capital: {plan_res.get('remaining_capital'):,.0f}\n"
        f"- Status: {'Success' if plan_res.get('target_achieved') else 'Partial'}\n"
        f"Details: {result.get('explanation')}"
    )

    return summary
