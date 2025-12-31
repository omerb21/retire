import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_build_target_pension_plan(*, args: dict, agent_tools: AgentToolsService) -> str:
    version_tag = "BUILD_TARGET_PENSION_PLAN_HANDLER_VERSION=2025-12-27.1"
    if not isinstance(args, dict):
        args = {}

    target = args.get("target_monthly_pension")
    try:
        target_val = float(target or 0)
    except Exception:
        target_val = 0
    if target_val <= 0:
        return "Error: Missing argument 'target_monthly_pension'"

    retirement_age = args.get("retirement_age")
    retirement_age_val = None
    if retirement_age is not None:
        try:
            retirement_age_val = int(retirement_age)
        except Exception:
            retirement_age_val = None

    target_is_net = args.get("target_is_net")
    if target_is_net is None:
        target_is_net_val = False
    else:
        target_is_net_val = bool(target_is_net)

    result = agent_tools.build_target_pension_plan(
        target_monthly_pension=target_val,
        retirement_age=retirement_age_val,
        target_is_net=target_is_net_val,
    )
    if not isinstance(result, dict):
        return (
            f"Tool Error: Unexpected tool response type ({type(result).__name__}).\n"
            f"{version_tag}"
        )

    if not result.get("success"):
        err_msg = None
        try:
            err_msg = str(result.get("explanation") or "").strip() or None
        except Exception:
            err_msg = None
        if err_msg is None:
            try:
                err_msg = str(result.get("error") or "").strip() or None
            except Exception:
                err_msg = None
        if err_msg is None:
            err_msg = f"Unknown error. raw_result_keys={sorted(list(result.keys()))}"
        return f"Tool Error: {err_msg}\n{version_tag}"

    plan_res = result.get("result", {})

    portfolio_sources_total = plan_res.get("portfolio_sources_total")
    portfolio_sources_added = plan_res.get("portfolio_sources_added")
    portfolio_sources_skipped_duplicates = plan_res.get("portfolio_sources_skipped_duplicates")
    portfolio_sources_total_balance = plan_res.get("portfolio_sources_total_balance")

    portfolio_diag = ""
    if any(
        val is not None
        for val in (
            portfolio_sources_total,
            portfolio_sources_added,
            portfolio_sources_skipped_duplicates,
            portfolio_sources_total_balance,
        )
    ):
        try:
            total_balance_text = (
                f"{float(portfolio_sources_total_balance):,.0f}"
                if portfolio_sources_total_balance is not None
                else "N/A"
            )
        except Exception:
            total_balance_text = "N/A"

        portfolio_diag = (
            "\n\nאבחון מסלקה (pension_portfolio_snapshot):\n"
            f"- מקורות שנמצאו: {portfolio_sources_total if portfolio_sources_total is not None else 'N/A'}\n"
            f"- מקורות שנוספו לתכנון: {portfolio_sources_added if portfolio_sources_added is not None else 'N/A'}\n"
            f"- מקורות שסוננו ככפילויות: {portfolio_sources_skipped_duplicates if portfolio_sources_skipped_duplicates is not None else 'N/A'}\n"
            f"- סה\"כ יתרה במסלקה שנקראה: {total_balance_text} ₪"
        )

    summary = (
        "תכנית יעד קצבה – סיכום:\n"
        f"- יעד קצבה חודשי: {plan_res.get('target_monthly_pension'):,.0f} ₪\n"
        f"- קצבה שהושגה מהמקורות שנבחרו: {plan_res.get('accumulated_pension'):,.0f} ₪\n"
        f"- הון שנותר (לא הומר לקצבה): {plan_res.get('remaining_capital'):,.0f} ₪\n"
        f"- סטטוס: {'היעד הושג' if plan_res.get('target_achieved') else 'היעד לא הושג במלואו'}\n"
        f"פירוט: {result.get('explanation')}\n"
        f"{portfolio_diag}\n"
        f"{version_tag}"
    )

    try:
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": {
                "target_monthly_pension": target_val,
                "target_is_net": target_is_net_val,
                "retirement_age": retirement_age_val,
            },
            "result": plan_res,
        }
        summary += (
            "\n\n###TARGET_PENSION_PLAN_DATA###\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n###END_TARGET_PENSION_PLAN_DATA###"
        )
    except Exception:
        pass

    return summary
