import json

from app.services.llm_agent_tools_service import AgentToolsService


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def handle_run_retirement_scenarios(*, args: dict, agent_tools: AgentToolsService) -> str:
    retirement_age = args.get("retirement_age")
    if retirement_age is None:
        return "Error: Missing argument 'retirement_age'"

    include_current_employer_termination = _as_bool(
        args.get("include_current_employer_termination", False)
    )

    result = agent_tools.run_retirement_scenarios(
        retirement_age=int(retirement_age),
        pension_portfolio=agent_tools.pension_portfolio_data,
        include_current_employer_termination=include_current_employer_termination,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
