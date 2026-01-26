import json

from app.services.llm_agent_tools_service import AgentToolsService


def handle_build_target_pension_plan(*, args: dict, agent_tools: AgentToolsService) -> str:
    version_tag = "BUILD_TARGET_PENSION_PLAN_HANDLER_VERSION=2026-01-01.1"
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
        target_is_net_val = True
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

    try:
        achieved_gross = float(plan_res.get("accumulated_pension") or 0)
    except Exception:
        achieved_gross = 0.0

    try:
        remaining_capital = float(plan_res.get("remaining_capital") or 0)
    except Exception:
        remaining_capital = 0.0

    mode_label = "נטו" if plan_res.get("target_is_net") else "ברוטו"
    status_label = "היעד הושג" if plan_res.get("target_achieved") else "היעד לא הושג במלואו"

    summary_lines: list[str] = []
    summary_lines.append("תכנית יעד קצבה – סיכום:")
    if retirement_age_val is not None:
        summary_lines.append(f"- גיל פרישה בתכנון: {int(retirement_age_val)}")
    summary_lines.append(f"- יעד קצבה חודשי ({mode_label}): {float(plan_res.get('target_monthly_pension') or 0):,.0f} ₪")

    if plan_res.get("target_is_net"):
        required_gross = plan_res.get("required_gross_for_target")
        estimated_tax = plan_res.get("estimated_monthly_tax")
        estimated_net = plan_res.get("estimated_monthly_net")
        if required_gross is not None:
            try:
                summary_lines.append(f"- ברוטו שנדרש כדי להגיע ליעד נטו (לפי הערכת מס): {float(required_gross):,.0f} ₪/חודש")
            except Exception:
                pass
        summary_lines.append(f"- קצבה ברוטו שנבנתה מהמקורות: {achieved_gross:,.0f} ₪/חודש")
        if estimated_tax is not None:
            try:
                summary_lines.append(f"- מס חודשי משוער: {float(estimated_tax):,.0f} ₪")
            except Exception:
                pass
        if estimated_net is not None:
            try:
                summary_lines.append(f"- קצבה נטו משוערת (אחרי מס הכנסה בלבד): {float(estimated_net):,.0f} ₪/חודש")
            except Exception:
                pass
    else:
        summary_lines.append(f"- קצבה ברוטו שהושגה מהמקורות שנבחרו: {achieved_gross:,.0f} ₪/חודש")

    summary_lines.append(f"- הון שנותר (לא הומר לקצבה): {remaining_capital:,.0f} ₪")
    summary_lines.append(f"- סטטוס: {status_label}")
    summary_lines.append(f"פירוט: {result.get('explanation')}")
    if portfolio_diag:
        summary_lines.append(portfolio_diag)
    summary_lines.append(version_tag)
    summary = "\n".join([line for line in summary_lines if isinstance(line, str)]).strip()

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
