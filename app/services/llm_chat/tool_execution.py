import inspect
import json
import logging
import threading as _threading
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.services.llm_agent_tools_service import AgentToolsService
from app.utils.llm_chat_log import get_current_case_id, get_current_request_id, log_llm_event
from app.services.llm_chat.tool_handlers.create_additional_income import (
    handle_create_additional_income,
)
from app.services.llm_chat.tool_handlers.create_individual_asset import (
    handle_create_individual_asset,
)
from app.services.llm_chat.tool_handlers.create_tax_exempt_grant import (
    handle_create_tax_exempt_grant,
)
from app.services.llm_chat.tool_handlers.execute_work_termination import (
    handle_execute_work_termination,
)
from app.services.llm_chat.tool_handlers.generate_full_report import handle_generate_full_report
from app.services.llm_chat.tool_handlers.generate_tax_deduction_documents import (
    handle_generate_tax_deduction_documents,
)
from app.services.llm_chat.tool_handlers.get_account_details import handle_get_account_details
from app.services.llm_chat.tool_handlers.get_tax_projection import handle_get_tax_projection
from app.services.llm_chat.tool_handlers.process_termination import handle_process_termination
from app.services.llm_chat.tool_handlers.project_total_annuity import handle_project_total_annuity
from app.services.llm_chat.tool_handlers.run_retirement_cashflow_analysis import (
    handle_run_retirement_cashflow_analysis,
)
from app.services.llm_chat.tool_handlers.set_current_employer_details import (
    handle_set_current_employer_details,
)
from app.services.llm_chat.tool_handlers.submit_tax_commutation import handle_submit_tax_commutation
from app.services.llm_chat.tool_handlers.transform_funds_to_assets import (
    handle_transform_funds_to_assets,
)
from app.services.llm_chat.tool_handlers.calculate_pension_commutation import (
    handle_calculate_pension_commutation,
)
from app.services.llm_chat.tool_handlers.build_target_pension_plan import (
    handle_build_target_pension_plan,
)
from app.services.llm_chat.tool_handlers.get_pension_products import handle_get_pension_products
from app.services.llm_chat.tool_handlers.calculate_tax_exempt_pension import (
    handle_calculate_tax_exempt_pension,
)
from app.services.llm_chat.tool_handlers.calculate_capital_withdrawal_tax import (
    handle_calculate_capital_withdrawal_tax,
)
from app.services.llm_chat.tool_handlers.calculate_tax_spread_benefit import (
    handle_calculate_tax_spread_benefit,
)
from app.services.llm_chat.tool_handlers.calculate_fixation_of_rights import (
    handle_calculate_fixation_of_rights,
)
from app.services.llm_chat.tool_handlers.check_data_completeness import (
    handle_check_data_completeness,
)
from app.services.llm_chat.tool_handlers.run_retirement_scenarios import (
    handle_run_retirement_scenarios,
)
from app.services.llm_chat.tool_handlers.run_retirement_scenarios_preview import (
    handle_run_retirement_scenarios_preview,
)
from app.services.llm_chat.tool_handlers.select_target_pension_scenario import (
    handle_select_target_pension_scenario,
)
from app.services.llm_chat.tool_handlers.find_optimal_scenario import (
    handle_find_optimal_scenario,
)
from app.services.llm_chat.tool_handlers.execute_retirement_scenario import (
    handle_execute_retirement_scenario,
)
from app.services.llm_chat.tool_handlers.execute_pension_commutation import (
    handle_execute_pension_commutation,
)
from app.services.llm_chat.tool_handlers.get_system_state_snapshot import (
    handle_get_system_state_snapshot,
)
from app.services.llm_chat.tool_handlers.get_client_snapshot import (
    handle_get_client_snapshot,
)
from app.services.llm_chat.tool_handlers.get_system_numeric_constants import (
    handle_get_system_numeric_constants,
)
from app.services.llm_chat.tool_handlers.get_pension_portfolio_snapshot_history import (
    handle_get_pension_portfolio_snapshot_history,
)
from app.services.llm_chat.tool_handlers.monthly_pension_summary import (
    handle_monthly_pension_summary,
)
from app.services.llm_chat.tools.get_fixation_status_snapshot import (
    handle_get_fixation_status_snapshot,
)
from app.services.llm_chat.tool_handlers.restore_pension_portfolio_snapshot import (
    handle_restore_pension_portfolio_snapshot,
)
from app.services.llm_chat.tool_handlers.restore_system_snapshot import (
    handle_restore_system_snapshot,
)
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    store_pending_approval_request,
    store_undo_snapshot,
)
from app.services.snapshot_service import SnapshotService
from app.services.llm_chat.orchestration_utils import (
    normalize_tool_name,
    validate_tool_call_protocol_for_execution,
)
from app.services.agent_trace_logger import log_trace_event as _log_agent_trace
from app.services.agent_eyes.event_collector import emit_event as _eyes_emit
from app.services.llm_chat.orchestration_utils_parts.protocol import _extract_single_line_json_after_marker
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    build_default_termination_plan_preview,
    compute_blocked_balances_summary_from_portfolio,
    evaluate_blocked_balances_policy_for_build_target_plan,
    load_blocked_balances_notice_shown,
    load_current_employer_termination_plan_preview,
    load_current_employer_severance_execution_decision,
    store_current_employer_termination_plan_preview,
    termination_already_executed_for_client,
)

logger = logging.getLogger("app.llm_chat.tools")

_turn_dedup = _threading.local()


def _dedup_cache_key(tool_name: str, args: dict) -> str:
    """Build a stable cache key from tool_name + sorted args JSON."""
    try:
        args_str = json.dumps(args, sort_keys=True, ensure_ascii=False) if isinstance(args, dict) else "{}"
    except Exception:
        args_str = "{}"
    return f"{tool_name}::{args_str}"


def reset_turn_dedup_cache() -> None:
    """Call at the start of each turn/request to clear the dedup cache."""
    _turn_dedup.cache = {}


def _get_turn_cache() -> dict:
    if not hasattr(_turn_dedup, "cache"):
        _turn_dedup.cache = {}
    return _turn_dedup.cache


WRITE_TOOLS: set[str] = {
    "TRANSFORM_FUNDS_TO_ASSETS",
    "CREATE_TAX_EXEMPT_GRANT",
    "CREATE_ADDITIONAL_INCOME",
    "CREATE_INDIVIDUAL_ASSET",
    "SET_CURRENT_EMPLOYER_DETAILS",
    "EXECUTE_WORK_TERMINATION",
    "PROCESS_TERMINATION",
    "EXECUTE_PENSION_COMMUTATION",
    "SUBMIT_TAX_COMMUTATION",
    "CALCULATE_FIXATION_OF_RIGHTS",
    "EXECUTE_RETIREMENT_SCENARIO",
    "RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
    "RESTORE_SYSTEM_SNAPSHOT",
}


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


def _maybe_fill_default_retirement_date(*, tool_name: str, args: dict, client_obj: Client | None) -> None:
    if not isinstance(args, dict):
        return

    return

    tools_requiring_retirement_date = {
        "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
        "CALCULATE_PENSION_COMMUTATION",
        "PROJECT_TOTAL_ANNUITY",
    }
    if tool_name not in tools_requiring_retirement_date:
        return

    val = args.get("retirement_date")
    if isinstance(val, str):
        should_fill = _is_placeholder_date_str(val)
    else:
        should_fill = val is None

    if not should_fill:
        return

    birth_date = getattr(client_obj, "birth_date", None) if client_obj else None
    gender = getattr(client_obj, "gender", None) if client_obj else None
    default_date_str = compute_default_retirement_date_for_tool_call(
        birth_date=birth_date,
        gender=gender,
        user_message="",
    )
    args["retirement_date"] = default_date_str


def _is_high_risk_risk_review(risk_review: dict[str, Any] | None) -> bool:
    if not isinstance(risk_review, dict):
        return False
    try:
        level = str(risk_review.get("risk_level") or "").strip().lower()
    except Exception:
        level = ""
    return level in {"high", "גבוה", "גבוהה"}


def execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
    force_max_exemption: bool = False,
    agent_reply: str | None = None,
    user_approved: bool = False,
    tool_call_id: str | None = None,
) -> str:
    original_tool_name = tool_name
    tool_name = normalize_tool_name(tool_name) or tool_name
    if original_tool_name != tool_name:
        try:
            _log_agent_trace(
                event_type="args_normalized",
                payload={
                    "normalizer_name": "normalize_tool_name",
                    "before": {"tool_name": original_tool_name},
                    "after": {"tool_name": tool_name},
                },
                client_id=client_id,
            )
        except Exception:
            pass
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)

    if tool_name not in WRITE_TOOLS:
        _cache = _get_turn_cache()
        _ckey = _dedup_cache_key(tool_name, args)
        if _ckey in _cache:
            logger.info("DEDUP_HIT tool=%s — returning cached result", tool_name)
            return _cache[_ckey]

    if tool_name == "PROCESS_TERMINATION":
        preview_payload = None
        try:
            preview_payload = load_current_employer_termination_plan_preview(
                db=db,
                client_id=int(client_id),
            )
        except Exception:
            preview_payload = None

        preview_approved = False
        preview_declined = False
        args_template = None
        if isinstance(preview_payload, dict):
            preview_approved = bool(preview_payload.get("approved")) is True
            preview_declined = bool(preview_payload.get("declined")) is True
            args_template = preview_payload.get("termination_arguments_template")

        if preview_approved and isinstance(args_template, dict) and args_template:
            args = dict(args_template)
        else:
            if preview_declined and (not preview_approved):
                return (
                    "לא אבצע תכנית ברירת מחדל לעזיבת עבודה בלי בחירה מפורשת. "
                    "אנא ציין מה לעשות עם הפיצויים (פטור/חייב)."
                )

            preview_text, default_template = build_default_termination_plan_preview(
                current_employer_amount=0.0,
                context=None,
            )
            template_to_store = (
                dict(args_template)
                if isinstance(args_template, dict) and args_template
                else dict(default_template)
            )
            try:
                store_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id),
                    payload={
                        "plan_args": {},
                        "termination_arguments_template": template_to_store,
                        "awaiting_user_confirmation": True,
                        "approved": False,
                        "declined": False,
                    },
                )
            except Exception:
                pass

            return preview_text

    case_id = get_current_case_id()
    if case_id == "interactive_readonly" and (not user_approved) and tool_name in WRITE_TOOLS:
        req_id = get_current_request_id() or "unknown"
        payload = {
            "request_id": req_id,
            "case_id": case_id,
            "tool_name": tool_name,
            "error": "TOOL_NOT_ALLOWED",
        }
        try:
            log_llm_event(
                request_id=req_id,
                event_type="tool_blocked",
                payload=payload,
                client_id=client_id,
            )
        except Exception:
            pass

        return json.dumps(
            {
                "success": False,
                "error": "TOOL_NOT_ALLOWED",
                "tool_name": tool_name,
            },
            ensure_ascii=False,
        )

    if tool_name in {"EXECUTE_PENSION_COMMUTATION", "SUBMIT_TAX_COMMUTATION"} and not user_approved:
        try:
            store_pending_approval_request(
                db=db,
                client_id=client_id,
                tool_name=tool_name,
                tool_args=args if isinstance(args, dict) else {},
            )
        except Exception:
            pass

        reason = "נדרש אישור לפני ביצוע פעולה במערכת."
        if tool_name == "EXECUTE_PENSION_COMMUTATION":
            reason = "נדרש אישור לפני ביצוע היוון קצבה במערכת."
        if tool_name == "SUBMIT_TAX_COMMUTATION":
            reason = "נדרש אישור לפני הגשת/ביצוע קיבוע/פריסה במערכת."

        return build_approval_request_ui_action(
            tool_name=tool_name,
            tool_args=args if isinstance(args, dict) else {},
            reason=reason,
            risk_level="high",
            rag_sources=None,
        )

    def enforce_blocked_balances_policy_for_build(*, plan_args_in: dict) -> tuple[str, dict, str | None]:
        plan_args_local = plan_args_in if isinstance(plan_args_in, dict) else {}
        portfolio = pension_portfolio or []

        summary = None
        try:
            summary = compute_blocked_balances_summary_from_portfolio(portfolio)
        except Exception:
            summary = None

        notice_shown = None
        decision = None
        term_executed = None
        try:
            notice_shown = load_blocked_balances_notice_shown(db=db, client_id=int(client_id))
        except Exception:
            notice_shown = None
        try:
            decision = load_current_employer_severance_execution_decision(db=db, client_id=int(client_id))
        except Exception:
            decision = None
        try:
            term_executed = termination_already_executed_for_client(db=db, client_id=int(client_id))
        except Exception:
            term_executed = None

        status = "proceed"
        updated_args = dict(plan_args_local) if isinstance(plan_args_local, dict) else {}
        policy_text = None
        try:
            status, updated_args, policy_text = evaluate_blocked_balances_policy_for_build_target_plan(
                db=db,
                client_id=int(client_id),
                portfolio=portfolio,
                plan_args=plan_args_local,
            )
        except Exception:
            status = "proceed"
            updated_args = plan_args_local
            policy_text = None

        try:
            payload = {
                "tool_name": tool_name,
                "policy_status": status,
                "notice_shown": notice_shown,
                "current_employer_decision": decision,
                "termination_already_executed": term_executed,
                "amounts": {
                    "non_settled": float(getattr(summary, "non_settled_severance_amount", 0) or 0)
                    if summary is not None
                    else None,
                    "continuity_rights": float(
                        getattr(summary, "prior_employers_continuity_rights_amount", 0) or 0
                    )
                    if summary is not None
                    else None,
                    "current_employer": float(getattr(summary, "current_employer_severance_amount", 0) or 0)
                    if summary is not None
                    else None,
                },
            }
            logger.info("BLOCKED_BALANCES_POLICY_APPLIED %s", json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

        return status, updated_args if isinstance(updated_args, dict) else plan_args_local, policy_text

    if tool_name == "BUILD_TARGET_PENSION_PLAN" and isinstance(args, dict):
        # ── Unified income offset: subtract AdditionalIncome (other income) ──
        # Applied here so that BOTH the deterministic path and the tool-call
        # loop produce the same effective target for the adapter.
        _offset_breakdown = None
        try:
            from app.services.llm_chat.orchestration_utils_parts.existing_income_offset import (
                compute_effective_plan_target,
            )
            _raw_target = float(args.get("target_monthly_pension") or 0)
            _is_net = args.get("target_is_net")
            _is_net_val = True if _is_net is None else bool(_is_net)
            if _raw_target > 0:
                _bd = compute_effective_plan_target(
                    db=db, client_id=int(client_id),
                    desired_total=_raw_target, target_is_net=_is_net_val,
                )
                _offset_breakdown = _bd
                args = dict(args)
                args["target_monthly_pension"] = _bd.effective_plan_target
                args["_target_breakdown"] = _bd.to_dict()
        except Exception:
            pass

        try:
            _effective_target = float((args or {}).get("target_monthly_pension") or 0)
        except Exception:
            _effective_target = 0.0
        if _offset_breakdown is not None and _effective_target <= 0:
            mode_label = "נטו" if bool(getattr(_offset_breakdown, "target_is_net", True)) else "ברוטו"
            lines: list[str] = []
            lines.append("✅ חישוב דטרמיניסטי:")
            lines.append(f"- יעד חודשי מבוקש ({mode_label}): התקבל")
            lines.append(f"- קיזוז הכנסות נוספות ({mode_label}): בוצע")
            lines.append("היעד כבר מושג מהכנסות קיימות – אין צורך בבניית קצבה נוספת בתכנית.")
            return "\n".join(lines).strip()

        policy_text = None
        policy_status, updated_args, policy_text = enforce_blocked_balances_policy_for_build(plan_args_in=args)
        args = updated_args if isinstance(updated_args, dict) else args

        if policy_status in {
            "ask_current_employer_termination",
            "needs_termination_plan_confirmation",
            "needs_termination_plan_alternative",
        }:
            return str(policy_text or "")

        if policy_status == "needs_termination_approval" and not user_approved:
            termination_args = {"confirmed": True}
            try:
                preview_payload = load_current_employer_termination_plan_preview(
                    db=db,
                    client_id=int(client_id),
                )
            except Exception:
                preview_payload = None

            if isinstance(preview_payload, dict):
                approved = bool(preview_payload.get("approved")) is True
                declined = bool(preview_payload.get("declined")) is True
                template = preview_payload.get("termination_arguments_template")
                if declined and (not approved):
                    return (
                        "לא אבצע תכנית ברירת מחדל לעזיבת עבודה בלי בחירה מפורשת. "
                        "אנא ציין מה לעשות עם הפיצויים (פטור/חייב)."
                    )
                if approved and isinstance(template, dict) and template:
                    termination_args = dict(template)

            try:
                store_pending_approval_request(
                    db=db,
                    client_id=client_id,
                    tool_name="PROCESS_TERMINATION",
                    tool_args=termination_args,
                )
            except Exception:
                pass
            return build_approval_request_ui_action(
                tool_name="PROCESS_TERMINATION",
                tool_args=termination_args,
                reason="נדרש אישור לפני ביצוע עזיבת עבודה במערכת.",
                risk_level="high",
                rag_sources=None,
            )

        if isinstance(policy_text, str) and policy_text.strip():
            args["_policy_notice_text"] = policy_text.strip()

    if tool_name == "RESTORE_SYSTEM_SNAPSHOT" and (not user_approved):
        try:
            store_pending_approval_request(
                db=db,
                client_id=client_id,
                tool_name=tool_name,
                tool_args=args if isinstance(args, dict) else {},
            )
        except Exception:
            pass

        return build_approval_request_ui_action(
            tool_name=tool_name,
            tool_args=args if isinstance(args, dict) else {},
            reason="נדרש אישור לפני שחזור מצב מערכת קודם.",
            risk_level="high",
            rag_sources=None,
        )

    if tool_name in WRITE_TOOLS and user_approved and tool_name not in {
        "RESTORE_PENSION_PORTFOLIO_SNAPSHOT",
        "RESTORE_SYSTEM_SNAPSHOT",
    }:
        try:
            snap = SnapshotService(db).save_snapshot(
                client_id,
                snapshot_name=f"undo_before_{tool_name}",
            )
            if isinstance(snap, dict):
                snap_payload = dict(snap)
                snap_payload["force_restore"] = True
                store_undo_snapshot(db=db, client_id=client_id, snapshot_payload=snap_payload)
        except Exception:
            pass

    if tool_name == "PROCESS_TERMINATION" and isinstance(args, dict):
        try:
            from app.utils.date_serializer import parse_date_flexible
            from app.models.current_employment import EmployerGrant, GrantType

            termination_date = None
            raw_date = args.get("termination_date")
            if raw_date is None or (isinstance(raw_date, str) and not raw_date.strip()):
                termination_date = None
            else:
                termination_date = parse_date_flexible(str(raw_date))

            if termination_date is not None:
                employer = (
                    db.query(CurrentEmployer)
                    .filter(CurrentEmployer.client_id == client_id)
                    .first()
                )

                if employer and employer.end_date and employer.end_date == termination_date:
                    grants_count = (
                        db.query(EmployerGrant)
                        .filter(
                            EmployerGrant.employer_id == employer.id,
                            EmployerGrant.grant_type == GrantType.severance,
                        )
                        .count()
                    )

                    confirmed = False
                    try:
                        other_grants = employer.other_grants or {}
                        if isinstance(other_grants, dict):
                            confirmed = bool(other_grants.get("termination_confirmed")) and (
                                other_grants.get("termination_date") == termination_date.isoformat()
                            )
                    except Exception:
                        confirmed = False

                    if confirmed and grants_count > 0:
                        return json.dumps(
                            {
                                "success": True,
                                "message": "עזיבת העבודה כבר בוצעה עבור התאריך הזה. לא בוצעו שינויים.",
                                "details": {
                                    "termination_date": str(termination_date),
                                    "already_processed": True,
                                    "evidence": {
                                        "termination_confirmed": True,
                                        "severance_grants_count": grants_count,
                                    },
                                },
                            },
                            ensure_ascii=False,
                        )
        except Exception:
            pass

    client_obj = db.query(Client).filter(Client.id == client_id).first()

    _maybe_fill_default_retirement_date(
        tool_name=tool_name,
        args=args if isinstance(args, dict) else {},
        client_obj=client_obj,
    )

    agent_tools = AgentToolsService(
        db,
        client_id,
        client_object=client_obj,
        pension_portfolio_data=pension_portfolio,
    )

    tool_call_id_local = tool_call_id

    try:
        _tc_payload = {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id_local,
            "args": args if isinstance(args, dict) else str(args)[:2000],
            "original_tool_name": original_tool_name,
            "client_id": client_id,
            "user_approved": user_approved,
            "force_max_exemption": force_max_exemption,
        }
        _log_agent_trace(event_type="tool_call", payload=_tc_payload, client_id=client_id)
        _eyes_emit("tool_call", _tc_payload, client_id=client_id)
    except Exception:
        pass

    _tool_exec_start = __import__("time").time()

    def _dispatch() -> str:
        if tool_name == "GET_SYSTEM_NUMERIC_CONSTANTS":
            return handle_get_system_numeric_constants(args=args)

        if tool_name == "MONTHLY_PENSION_SUMMARY":
            return handle_monthly_pension_summary(args=args, client_id=client_id, db=db)

        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            return handle_build_target_pension_plan(args=args, agent_tools=agent_tools)

        if tool_name == "GET_TAX_PROJECTION":
            return handle_get_tax_projection(
                args=args,
                client_id=client_id,
                db=db,
                agent_tools=agent_tools,
            )

        if tool_name == "GET_TAX_PARAMS":
            tax_year = None
            if isinstance(args, dict):
                raw_tax_year = args.get("tax_year")
                if raw_tax_year is not None:
                    try:
                        tax_year = int(raw_tax_year)
                    except Exception:
                        return "Error: invalid tax_year"
            result = agent_tools.get_tax_params(tax_year=tax_year)
            return json.dumps(result, ensure_ascii=False)

        if tool_name == "GET_PENSION_PRODUCTS":
            return handle_get_pension_products(agent_tools=agent_tools)

        if tool_name == "CHECK_DATA_COMPLETENESS":
            return handle_check_data_completeness(agent_tools=agent_tools)

        if tool_name == "CALCULATE_TAX_EXEMPT_PENSION":
            return handle_calculate_tax_exempt_pension(args=args, agent_tools=agent_tools)

        if tool_name == "RUN_RETIREMENT_CASHFLOW_ANALYSIS":
            return handle_run_retirement_cashflow_analysis(
                args=args,
                agent_tools=agent_tools,
                force_max_exemption=force_max_exemption,
            )

        if tool_name == "RUN_RETIREMENT_SCENARIOS":
            preview_flag = False
            try:
                raw_preview = args.get("preview") if isinstance(args, dict) else None
                if isinstance(raw_preview, str):
                    preview_flag = raw_preview.strip().lower() in {"true", "1", "yes", "y"}
                else:
                    preview_flag = bool(raw_preview)
            except Exception:
                preview_flag = False

            if preview_flag:
                return handle_run_retirement_scenarios_preview(args=args, agent_tools=agent_tools)
            return handle_run_retirement_scenarios(args=args, agent_tools=agent_tools)

        if tool_name == "SELECT_TARGET_PENSION_SCENARIO":
            return handle_select_target_pension_scenario(args=args, agent_tools=agent_tools)

        if tool_name == "FIND_OPTIMAL_SCENARIO":
            return handle_find_optimal_scenario(args=args, agent_tools=agent_tools)

        if tool_name == "EXECUTE_RETIREMENT_SCENARIO":
            return handle_execute_retirement_scenario(
                args=args,
                client_id=client_id,
                db=db,
            )

        if tool_name == "CALCULATE_PENSION_COMMUTATION":
            return handle_calculate_pension_commutation(
                args=args,
                agent_tools=agent_tools,
            )

        if tool_name == "CALCULATE_CAPITAL_WITHDRAWAL_TAX":
            return handle_calculate_capital_withdrawal_tax(args=args, agent_tools=agent_tools)

        if tool_name == "CALCULATE_TAX_SPREAD_BENEFIT":
            return handle_calculate_tax_spread_benefit(args=args, agent_tools=agent_tools)

        if tool_name == "PROCESS_TERMINATION":
            return handle_process_termination(
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
            )

        if tool_name == "PROJECT_TOTAL_ANNUITY":
            return handle_project_total_annuity(
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
            )

        if tool_name == "GET_ACCOUNT_DETAILS":
            return handle_get_account_details(
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
            )

        if tool_name == "SUBMIT_TAX_COMMUTATION":
            return handle_submit_tax_commutation(
                args=args,
                client_id=client_id,
                client_obj=client_obj,
            )

        if tool_name == "EXECUTE_PENSION_COMMUTATION":
            return handle_execute_pension_commutation(
                args=args,
                client_id=client_id,
                db=db,
            )

        if tool_name == "GENERATE_FULL_REPORT":
            return handle_generate_full_report(
                args=args,
                client_id=client_id,
                db=db,
                client_obj=client_obj,
                agent_tools=agent_tools,
            )

        if tool_name == "GENERATE_TAX_DEDUCTION_DOCUMENTS":
            return handle_generate_tax_deduction_documents(
                args=args,
                client_id=client_id,
                db=db,
                client_obj=client_obj,
            )

        if tool_name == "GET_SYSTEM_STATE_SNAPSHOT":
            return handle_get_system_state_snapshot(args=args, client_id=client_id, db=db)

        if tool_name == "GET_CLIENT_SNAPSHOT":
            return handle_get_client_snapshot(args=args, client_id=client_id, db=db)

        if tool_name == "GET_PENSION_PORTFOLIO_SNAPSHOT_HISTORY":
            return handle_get_pension_portfolio_snapshot_history(
                args=args,
                client_id=client_id,
                db=db,
            )

        if tool_name == "GET_FIXATION_STATUS_SNAPSHOT":
            return handle_get_fixation_status_snapshot(args=args, client_id=client_id, db=db)

        # ===== OPERATION TOOLS - Data Input & Transformation =====

        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            return handle_transform_funds_to_assets(
                args=args,
                client_id=client_id,
                db=db,
                agent_tools=agent_tools,
            )

        if tool_name == "RESTORE_PENSION_PORTFOLIO_SNAPSHOT":
            return handle_restore_pension_portfolio_snapshot(
                args=args,
                client_id=client_id,
                db=db,
            )

        if tool_name == "RESTORE_SYSTEM_SNAPSHOT":
            return handle_restore_system_snapshot(
                args=args,
                client_id=client_id,
                db=db,
            )

        if tool_name == "CREATE_TAX_EXEMPT_GRANT":
            return handle_create_tax_exempt_grant(args=args, client_id=client_id, db=db)

        if tool_name == "CREATE_ADDITIONAL_INCOME":
            return handle_create_additional_income(args=args, client_id=client_id, db=db)

        if tool_name == "CREATE_INDIVIDUAL_ASSET":
            return handle_create_individual_asset(args=args, client_id=client_id, db=db)

        # ===== OPERATION TOOLS - Process Tools =====

        if tool_name == "SET_CURRENT_EMPLOYER_DETAILS":
            return handle_set_current_employer_details(args=args, client_id=client_id, db=db)

        if tool_name == "EXECUTE_WORK_TERMINATION":
            return handle_execute_work_termination(args=args, client_id=client_id, db=db)

        if tool_name == "PROCESS_TERMINATION":
            return handle_process_termination(
                args=args,
                client_id=client_id,
                db=db,
                pension_portfolio=pension_portfolio,
            )

        if tool_name == "CALCULATE_FIXATION_OF_RIGHTS":
            return handle_calculate_fixation_of_rights(
                args=args,
                client_id=client_id,
                db=db,
                client_obj=client_obj,
            )

        _known_tools = [
            "GET_SYSTEM_STATE_SNAPSHOT", "GET_CLIENT_SNAPSHOT",
            "GET_FIXATION_STATUS_SNAPSHOT", "GET_SYSTEM_NUMERIC_CONSTANTS",
            "BUILD_TARGET_PENSION_PLAN", "GET_TAX_PROJECTION", "GET_TAX_PARAMS",
            "GET_PENSION_PRODUCTS", "CHECK_DATA_COMPLETENESS",
            "CALCULATE_TAX_EXEMPT_PENSION", "RUN_RETIREMENT_CASHFLOW_ANALYSIS",
            "RUN_RETIREMENT_SCENARIOS", "SELECT_TARGET_PENSION_SCENARIO",
            "FIND_OPTIMAL_SCENARIO", "EXECUTE_RETIREMENT_SCENARIO",
            "CALCULATE_PENSION_COMMUTATION", "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
            "CALCULATE_TAX_SPREAD_BENEFIT", "PROCESS_TERMINATION",
            "PROJECT_TOTAL_ANNUITY", "GET_ACCOUNT_DETAILS",
            "SUBMIT_TAX_COMMUTATION", "EXECUTE_PENSION_COMMUTATION",
            "GENERATE_FULL_REPORT", "GENERATE_TAX_DEDUCTION_DOCUMENTS",
            "TRANSFORM_FUNDS_TO_ASSETS", "CREATE_TAX_EXEMPT_GRANT",
            "CREATE_ADDITIONAL_INCOME", "CREATE_INDIVIDUAL_ASSET",
            "SET_CURRENT_EMPLOYER_DETAILS", "EXECUTE_WORK_TERMINATION",
            "CALCULATE_FIXATION_OF_RIGHTS",
            "GET_PENSION_PORTFOLIO_SNAPSHOT_HISTORY",
            "RESTORE_PENSION_PORTFOLIO_SNAPSHOT", "RESTORE_SYSTEM_SNAPSHOT",
        ]
        return json.dumps({
            "error": f"Tool '{tool_name}' not found.",
            "available_tools": _known_tools,
        }, ensure_ascii=False)

    # --- execute dispatch, log tool_result, return ---
    try:
        result = _dispatch()
    except Exception as e:
        elapsed_ms = int((__import__("time").time() - _tool_exec_start) * 1000)
        logger.error("Tool execution failed: %s", e, exc_info=True)
        try:
            import traceback as _tb_mod
            _err_payload = {
                "tool_name": tool_name,
                "error_type": type(e).__name__,
                "error_message": str(e)[:2000],
                "stack_trace": _tb_mod.format_exc()[:4000],
                "elapsed_ms": elapsed_ms,
            }
            _log_agent_trace(event_type="error", payload=_err_payload, client_id=client_id)
            _eyes_emit("error", _err_payload, client_id=client_id)
        except Exception:
            pass
        try:
            from app.services.agent_trace_logger import emit_trace_error
            emit_trace_error(exc=e, where="tool_execution:execute_tool_call", client_id=client_id)
        except Exception:
            pass
        return f"System Error while executing tool: {str(e)}"

    elapsed_ms = int((__import__("time").time() - _tool_exec_start) * 1000)
    try:
        _tr_payload = {
            "tool_name": tool_name,
            "tool_call_id": tool_call_id_local,
            "status": "ok",
            "success": True,
            "elapsed_ms": elapsed_ms,
            "result_preview": (result or "")[:2000],
            "result_length": len(result or ""),
        }
        _log_agent_trace(event_type="tool_result", payload=_tr_payload, client_id=client_id)
        _eyes_emit("tool_result", _tr_payload, client_id=client_id)
    except Exception:
        pass

    if tool_name not in WRITE_TOOLS:
        try:
            _cache = _get_turn_cache()
            _ckey = _dedup_cache_key(tool_name, args)
            _cache[_ckey] = result
        except Exception:
            pass

    return result
