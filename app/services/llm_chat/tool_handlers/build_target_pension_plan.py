import json
import logging

from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
    compute_effective_plan_target,
)

_logger = logging.getLogger("app.llm_chat.tool_handlers.build_target_pension_plan")


def _has_positive_component_amounts(raw: object) -> bool:
    if not isinstance(raw, dict) or not raw:
        return False
    for _k, v in raw.items():
        try:
            if float(v or 0) > 0:
                return True
        except Exception:
            continue
    return False


def _accounts_are_thin(accounts: object) -> bool:
    if not isinstance(accounts, list) or not accounts:
        return False

    def _get_account_number(acc: dict) -> str:
        return str(
            acc.get("account_number")
            or acc.get("מספר_חשבון")
            or acc.get("מספר חשבון")
            or acc.get("מספר-חשבון")
            or ""
        ).strip()

    for acc in accounts:
        if not isinstance(acc, dict):
            continue

        account_number = _get_account_number(acc)
        if not account_number:
            continue
        raw_balance = acc.get("balance")
        if raw_balance is None:
            raw_balance = acc.get("יתרה")
        if raw_balance is None:
            raw_balance = acc.get("current_balance")

        try:
            if float(raw_balance or 0) > 0:
                continue
        except Exception:
            pass

        if _has_positive_component_amounts(acc.get("specific_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_amounts")):
            continue
        if _has_positive_component_amounts(acc.get("selected_components")):
            continue

        return True

    return False


def handle_build_target_pension_plan(
    *, args: dict, agent_tools: AgentToolsService
) -> str:
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

    ignore_blocked_balances_raw = args.get("ignore_blocked_balances")
    ignore_blocked_balances_val = (
        True
        if ignore_blocked_balances_raw is None
        else bool(ignore_blocked_balances_raw)
    )

    # ── Income offset metadata ──
    # The offset is applied *before* the handler is called:
    #   - Deterministic path: compute_effective_plan_target() in generate_target_plan()
    #   - Tool-call loop:     compute_effective_plan_target() in tool_execution.py
    # The handler receives the already-reduced target_monthly_pension.
    # We only read the breakdown metadata here for display purposes.
    breakdown = None
    try:
        from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
            TargetPlanBreakdown,
        )

        _bd_raw = args.get("_target_breakdown")
        if isinstance(_bd_raw, dict):
            breakdown = TargetPlanBreakdown(**_bd_raw)
    except Exception:
        breakdown = None

    result = agent_tools.build_target_pension_plan(
        target_monthly_pension=target_val,
        retirement_age=retirement_age_val,
        target_is_net=target_is_net_val,
        ignore_blocked_balances=ignore_blocked_balances_val,
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
        if isinstance(err_msg, str) and ("לא נמצאו מקורות קצבה" in err_msg):
            summary = (
                "לא נמצאו מקורות קצבה לחישוב תכנית יעד קצבה עבור הלקוח. "
                "ודא שקיים תיק פנסיוני (מסלקה) עדכני או מקורות קצבה במערכת, ואז נסה שוב.\n"
                + version_tag
            )
            try:
                payload = {
                    "tool_name": "BUILD_TARGET_PENSION_PLAN",
                    "args": {
                        "target_monthly_pension": target_val,
                        "target_is_net": target_is_net_val,
                        "retirement_age": retirement_age_val,
                        "ignore_blocked_balances": ignore_blocked_balances_val,
                    },
                    "result": (
                        result.get("result")
                        if isinstance(result.get("result"), dict)
                        else {}
                    ),
                }
                summary += (
                    "\n\n###TARGET_PENSION_PLAN_DATA###\n"
                    + json.dumps(payload, ensure_ascii=False)
                    + "\n###END_TARGET_PENSION_PLAN_DATA###"
                )
            except Exception:
                pass
            return summary
        if err_msg is None:
            try:
                err_msg = str(result.get("error") or "").strip() or None
            except Exception:
                err_msg = None
        if err_msg is None:
            err_msg = f"Unknown error. raw_result_keys={sorted(list(result.keys()))}"
        return f"Tool Error: {err_msg}\n{version_tag}"

    plan_res = result.get("result", {})

    # ── Guardrail: implied_total_net consistency check ──
    try:
        if breakdown is not None and target_is_net_val and result.get("success"):
            _estimated_net_from_plan = float(plan_res.get("estimated_monthly_net") or 0)
            _other_income_net = float(breakdown.other_income_offset_net or 0)
            _implied_total_net = _estimated_net_from_plan + _other_income_net
            _desired = float(breakdown.desired_net_total or 0)
            _deviation = abs(_implied_total_net - _desired)
            _tolerance = max(500.0, _desired * 0.05)
            if _estimated_net_from_plan > 0 and _deviation > _tolerance:
                _logger.warning(
                    "GUARDRAIL_NET_CONSISTENCY: desired_net_total=%.0f "
                    "estimated_net_from_plan=%.0f other_income_net=%.0f "
                    "implied_total_net=%.0f deviation=%.0f tolerance=%.0f "
                    "client_id=%s",
                    _desired,
                    _estimated_net_from_plan,
                    _other_income_net,
                    _implied_total_net,
                    _deviation,
                    _tolerance,
                    agent_tools.client_id,
                )
    except Exception:
        pass

    portfolio_sources_total = plan_res.get("portfolio_sources_total")
    portfolio_sources_added = plan_res.get("portfolio_sources_added")
    portfolio_sources_skipped_duplicates = plan_res.get(
        "portfolio_sources_skipped_duplicates"
    )
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
            f'- סה"כ יתרה במסלקה שנקראה: {total_balance_text} ₪'
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
    status_label = (
        "היעד הושג" if plan_res.get("target_achieved") else "היעד לא הושג במלואו"
    )

    summary_lines: list[str] = []
    summary_lines.append("תכנית יעד קצבה – סיכום:")
    if retirement_age_val is not None:
        summary_lines.append(f"- גיל פרישה בתכנון: {int(retirement_age_val)}")
    if breakdown is not None:
        summary_lines.append(
            f"- יעד כולל מבוקש ({mode_label}): {breakdown.desired_net_total:,.0f} ₪"
        )
        _off = (
            breakdown.other_income_offset_net
            if target_is_net_val
            else breakdown.other_income_offset_gross
        )
        if _off > 0:
            summary_lines.append(f"- קיזוז הכנסות נוספות ({mode_label}): {_off:,.0f} ₪")
        summary_lines.append(
            f"- יעד קצבה לתכנית ({mode_label}, אחרי קיזוז הכנסות נוספות): {breakdown.effective_plan_target:,.0f} ₪"
        )
    else:
        summary_lines.append(
            f"- יעד קצבה חודשי ({mode_label}): {float(plan_res.get('target_monthly_pension') or 0):,.0f} ₪"
        )

    existing_katzba = plan_res.get("existing_katzba_total_gross")
    if existing_katzba is not None:
        try:
            existing_katzba_val = float(existing_katzba or 0)
        except Exception:
            existing_katzba_val = 0.0
        if existing_katzba_val > 0:
            summary_lines.append(
                f"- קצבאות קיימות במערכת (ברוטו): {existing_katzba_val:,.0f} ₪/חודש (מקוזז בתוך התכנית)"
            )

    if plan_res.get("target_is_net"):
        required_gross = plan_res.get("required_gross_for_target")
        estimated_tax = plan_res.get("estimated_monthly_tax")
        estimated_net = plan_res.get("estimated_monthly_net")
        if required_gross is not None:
            try:
                summary_lines.append(
                    f"- ברוטו שנדרש כדי להגיע ליעד נטו (לפי הערכת מס): {float(required_gross):,.0f} ₪/חודש"
                )
            except Exception:
                pass
        summary_lines.append(
            f"- קצבה ברוטו שנבנתה מהמקורות: {achieved_gross:,.0f} ₪/חודש"
        )
        if estimated_tax is not None:
            try:
                summary_lines.append(f"- מס חודשי משוער: {float(estimated_tax):,.0f} ₪")
            except Exception:
                pass
        if estimated_net is not None:
            try:
                summary_lines.append(
                    f"- קצבה נטו משוערת (אחרי מס הכנסה בלבד): {float(estimated_net):,.0f} ₪/חודש"
                )
            except Exception:
                pass
    else:
        summary_lines.append(
            f"- קצבה ברוטו שהושגה מהמקורות שנבחרו: {achieved_gross:,.0f} ₪/חודש"
        )

    summary_lines.append(f"- הון שנותר (לא הומר לקצבה): {remaining_capital:,.0f} ₪")
    summary_lines.append(f"- סטטוס: {status_label}")
    summary_lines.append(f"פירוט: {result.get('explanation')}")
    if portfolio_diag:
        summary_lines.append(portfolio_diag)
    summary_lines.append(version_tag)
    summary = "\n".join(
        [line for line in summary_lines if isinstance(line, str)]
    ).strip()

    try:
        payload = {
            "tool_name": "BUILD_TARGET_PENSION_PLAN",
            "args": {
                "target_monthly_pension": target_val,
                "target_is_net": target_is_net_val,
                "retirement_age": retirement_age_val,
                "ignore_blocked_balances": ignore_blocked_balances_val,
            },
            "offsets": breakdown.to_dict() if breakdown is not None else None,
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
