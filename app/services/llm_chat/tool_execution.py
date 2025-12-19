import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import (
    Client,
)
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.tool_handlers.calculate_fixation_of_rights import (
    handle_calculate_fixation_of_rights,
)
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
from app.services.llm_chat.tool_handlers.check_data_completeness import (
    handle_check_data_completeness,
)
from app.services.llm_chat.tool_handlers.run_retirement_scenarios import (
    handle_run_retirement_scenarios,
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

logger = logging.getLogger("app.llm_chat.tools")


def execute_tool_call(
    tool_name: str,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
    force_max_exemption: bool = False,
) -> str:
    logger.info("⚡ Executing Tool: %s with args: %s", tool_name, args)

    client_obj = db.query(Client).filter(Client.id == client_id).first()

    agent_tools = AgentToolsService(
        db,
        client_id,
        client_object=client_obj,
        pension_portfolio_data=pension_portfolio,
    )

    try:
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
