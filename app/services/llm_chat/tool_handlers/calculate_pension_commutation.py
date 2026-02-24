import json
import logging

from app.services.llm_agent_tools_service import AgentToolsService

logger = logging.getLogger("app.llm_chat.tools")


def handle_calculate_pension_commutation(
    *, args: dict, agent_tools: AgentToolsService
) -> str:
    reduction = args.get("target_monthly_pension_reduction")
    date_str = args.get("retirement_date")

    if reduction is None:
        return "Error: Missing argument 'target_monthly_pension_reduction'"
    if not date_str:
        return "Error: Missing argument 'retirement_date'"

    result = agent_tools.calculate_pension_commutation(
        target_monthly_pension_reduction=float(reduction),
        retirement_date=date_str,
    )

    if not result.get("success"):
        return f"Tool Error: {result.get('explanation')}"

    commutation_result = result.get("result", {})

    try:
        cashflow_result = agent_tools.run_retirement_cashflow_analysis(
            retirement_date=date_str,
            desired_monthly_income=None,
            apply_max_exemption=True,
        )

        if cashflow_result.get("success"):
            cashflow_data = cashflow_result.get("result", {})

            combined_result = {
                "commutation": commutation_result,
                "full_pension_comparison": {
                    "total_gross_pension": cashflow_data.get(
                        "total_guaranteed_income", 0
                    ),
                    "income_tax": cashflow_data.get("income_tax", 0),
                    "net_pension": cashflow_data.get("net_income", 0),
                    "exemption_percentage": cashflow_data.get(
                        "exemption_percentage", 0
                    ),
                },
                "comparison_summary": {
                    "lump_sum_net": commutation_result.get("lump_sum_net", 0),
                    "monthly_pension_lost": commutation_result.get(
                        "target_monthly_pension_reduction", 0
                    ),
                    "full_net_pension_without_commutation": cashflow_data.get(
                        "net_income", 0
                    ),
                    "recommendation": commutation_result.get(
                        "recommendation", "unknown"
                    ),
                },
                "_force_chained": True,
            }
            return json.dumps(combined_result, ensure_ascii=False)
    except Exception as chain_err:
        logger.warning(
            "Force chaining failed for CALCULATE_PENSION_COMMUTATION: %s",
            chain_err,
        )

    return json.dumps(commutation_result, ensure_ascii=False)
