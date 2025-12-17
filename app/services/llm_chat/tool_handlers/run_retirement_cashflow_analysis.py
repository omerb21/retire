import json
import logging

from app.services.llm_agent_tools_service import AgentToolsService

logger = logging.getLogger("app.llm_chat.tools")


def handle_run_retirement_cashflow_analysis(
    *,
    args: dict,
    agent_tools: AgentToolsService,
    force_max_exemption: bool,
) -> str:
    date_str = args.get("retirement_date")
    income = args.get("desired_monthly_income")
    apply_max_exemption_arg = args.get("apply_max_exemption", False)

    if not date_str:
        return "Error: Missing argument 'retirement_date'"

    income_val = float(income) if income else None

    if isinstance(apply_max_exemption_arg, str):
        apply_max_exemption = apply_max_exemption_arg.strip().lower() in {
            "true",
            "1",
            "yes",
            "y",
        }
    else:
        apply_max_exemption = bool(apply_max_exemption_arg)

    if force_max_exemption:
        apply_max_exemption = True

    result = agent_tools.run_retirement_cashflow_analysis(
        retirement_date=date_str,
        desired_monthly_income=income_val,
        apply_max_exemption=apply_max_exemption,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
