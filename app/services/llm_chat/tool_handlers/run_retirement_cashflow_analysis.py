import json
import logging

from app.services.llm_agent_tools_service import AgentToolsService

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
    desired_net_income = args.get("desired_net_monthly_income")
    desired_income_is_net = args.get("desired_income_is_net")
    apply_max_exemption_arg = args.get("apply_max_exemption", False)
    explicit_age = args.get("age")
    explicit_gender = args.get("gender")

    if date_str is None:
        date_str = ""

    if isinstance(date_str, str) and _is_placeholder_date_str(date_str):
        date_str = ""

    income_val = float(income) if income else None
    if desired_net_income is not None:
        try:
            income_val = float(desired_net_income)
            desired_income_is_net = True
        except Exception:
            pass

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
        explicit_age=explicit_age,
        explicit_gender=explicit_gender,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    # Return full payload so orchestration can use deterministic explanation.
    return json.dumps(result, ensure_ascii=False)
