import json

from app.services.llm_agent_tools_service import AgentToolsService, _to_jsonable
from app.services.retirement import RetirementScenariosBuilder


def handle_run_retirement_scenarios_preview(
    *, args: dict, agent_tools: AgentToolsService
) -> str:
    retirement_age = args.get("retirement_age")
    if retirement_age is None:
        return "Error: Missing argument 'retirement_age'"

    include_current_employer_termination = args.get(
        "include_current_employer_termination", False
    )
    if isinstance(include_current_employer_termination, str):
        include_current_employer_termination_val = (
            include_current_employer_termination.strip().lower()
            in {
                "true",
                "1",
                "yes",
                "y",
            }
        )
    else:
        include_current_employer_termination_val = bool(
            include_current_employer_termination
        )

    portfolio = getattr(agent_tools, "pension_portfolio_data", None)
    portfolio_serialized = _to_jsonable(portfolio) if portfolio is not None else None
    if portfolio_serialized is not None and not isinstance(portfolio_serialized, list):
        portfolio_serialized = None

    builder = RetirementScenariosBuilder(
        agent_tools.db,
        agent_tools.client_id,
        int(retirement_age),
        portfolio_serialized,
        include_current_employer_termination_val,
    )
    scenarios = builder.build_all_scenarios()

    if not isinstance(scenarios, dict) or not scenarios:
        return json.dumps(
            {
                "success": False,
                "tool_name": "RUN_RETIREMENT_SCENARIOS",
                "preview": True,
                "result": {},
                "explanation": "שגיאה בהפקת התרחישים (preview).",
            },
            ensure_ascii=False,
        )

    summary: list[dict] = []
    for key, data in scenarios.items():
        if not isinstance(data, dict):
            continue
        summary.append(
            {
                "scenario_key": key,
                "scenario_name": data.get("scenario_name"),
                "total_pension_monthly": data.get("total_pension_monthly", 0),
                "total_capital": data.get("total_capital", 0),
                "estimated_npv": data.get("estimated_npv", 0),
            }
        )

    max_pension = max(
        (float(s.get("total_pension_monthly") or 0) for s in summary), default=0.0
    )
    max_capital = max(
        (float(s.get("total_capital") or 0) for s in summary), default=0.0
    )
    max_npv = max((float(s.get("estimated_npv") or 0) for s in summary), default=0.0)

    return json.dumps(
        {
            "success": True,
            "tool_name": "RUN_RETIREMENT_SCENARIOS",
            "preview": True,
            "result": {
                "retirement_age": int(retirement_age),
                "scenarios": summary,
                "max_pension": max_pension,
                "max_capital": max_capital,
                "max_npv": max_npv,
            },
        },
        ensure_ascii=False,
    )
