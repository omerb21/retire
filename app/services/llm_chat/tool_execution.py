import inspect
import json
import logging
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
from app.services.llm_chat.tool_handlers.get_system_numeric_constants import (
    handle_get_system_numeric_constants,
)
from app.services.llm_chat.chat_orchestration_helpers import (
    build_approval_request_ui_action,
    store_pending_approval_request,
)
from app.services.llm_chat.orchestration_utils import (
    compute_default_retirement_date_for_tool_call,
    normalize_tool_name,
    validate_tool_call_protocol_for_execution,
)

logger = logging.getLogger("app.llm_chat.tools")


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
    "EXECUTE_RETIREMENT_SCENARIO",
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


def _extract_single_line_json_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    if marker not in (text or ""):
        return None

    after = text.split(marker, 1)[1].strip()
    json_str = after.strip("`").strip()
    json_str = json_str.splitlines()[0] if json_str else ""
    if not json_str:
        return None

    try:
        parsed = json.loads(json_str)
    except Exception:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


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
) -> str:
    tool_name = normalize_tool_name(tool_name) or tool_name
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)

    case_id = get_current_case_id()
    if case_id == "interactive_readonly" and tool_name in WRITE_TOOLS:
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

    try:
        if tool_name == "GET_SYSTEM_NUMERIC_CONSTANTS":
            return handle_get_system_numeric_constants(args=args)

        if tool_name == "BUILD_TARGET_PENSION_PLAN":
            return handle_build_target_pension_plan(args=args, agent_tools=agent_tools)

        if tool_name == "GET_TAX_PROJECTION":
            return handle_get_tax_projection(
                args=args,
                client_id=client_id,
                db=db,
                agent_tools=agent_tools,
            )

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

        # ===== OPERATION TOOLS - Data Input & Transformation =====

        if tool_name == "TRANSFORM_FUNDS_TO_ASSETS":
            return handle_transform_funds_to_assets(
                args=args,
                client_id=client_id,
                db=db,
                agent_tools=agent_tools,
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

        if tool_name == "CALCULATE_FIXATION_OF_RIGHTS":
            return handle_calculate_fixation_of_rights(
                args=args,
                client_id=client_id,
                db=db,
                client_obj=client_obj,
            )

        return f"Error: Tool '{tool_name}' not found."

    except Exception as e:
        logger.error("Tool execution failed: %s", e, exc_info=True)
        return f"System Error while executing tool: {str(e)}"
