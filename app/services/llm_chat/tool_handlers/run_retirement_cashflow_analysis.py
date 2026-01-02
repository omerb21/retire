import json
import logging

from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.orchestration_utils import compute_default_retirement_date_for_tool_call

logger = logging.getLogger("app.llm_chat.tools")


def _is_placeholder_date_str(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return True

    upper = raw.upper()
    if upper == "YYYY-MM-DD":
        return True

    if "YYYY" in upper or "MM" in upper or "DD" in upper:
        return True

    return False


def handle_run_retirement_cashflow_analysis(
    *,
    args: dict,
    agent_tools: AgentToolsService,
    force_max_exemption: bool,
) -> str:
    date_str = args.get("retirement_date")
    income = args.get("desired_monthly_income")
    desired_income_is_net = args.get("desired_income_is_net")
    apply_max_exemption_arg = args.get("apply_max_exemption", False)

    if not isinstance(date_str, str) or _is_placeholder_date_str(date_str):
        raw_before = date_str
        birth_date = None
        gender = None
        try:
            birth_date = getattr(getattr(agent_tools, "client", None), "birth_date", None)
        except Exception:
            birth_date = None
        try:
            gender = getattr(getattr(agent_tools, "client", None), "gender", None)
        except Exception:
            gender = None
        filled = compute_default_retirement_date_for_tool_call(
            birth_date=birth_date,
            gender=gender,
            user_message="",
        )
        logger.warning(
            "RUN_RETIREMENT_CASHFLOW_ANALYSIS: Replaced placeholder retirement_date=%s with %s (birth_date=%s)",
            raw_before,
            filled,
            birth_date,
        )
        if isinstance(args, dict):
            args["retirement_date"] = filled
        date_str = filled

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

    desired_income_is_net_val = None
    if desired_income_is_net is not None:
        desired_income_is_net_val = bool(desired_income_is_net)

    result = agent_tools.run_retirement_cashflow_analysis(
        retirement_date=date_str,
        desired_monthly_income=income_val,
        apply_max_exemption=apply_max_exemption,
        desired_income_is_net=desired_income_is_net_val,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    return json.dumps(result.get("result"), ensure_ascii=False)
