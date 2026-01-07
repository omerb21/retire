import logging

logger = logging.getLogger("app.llm_chat.tools")


def build_transform_funds_response(
    *,
    success: bool,
    message: str,
    converted_pensions: int,
    converted_capitals: int,
    converted_commutations: int,
    total_converted: int,
    skipped_accounts: int,
    skipped_non_convertible,
    converted_items,
    skipped_items,
    blocked_field_amount: float,
    employer_current_severance_total: float,
    errors,
    scenarios_updated: int,
    scenario_source_cleanup_ok,
    source_pension_funds_zeroed: int,
    next_step: str | None = None,
    source_data_cleared: bool = False,
    memory_cleared: bool = False,
) -> dict:
    response = {
        "success": success,
        "message": message,
        "converted_pensions": converted_pensions,
        "converted_capitals": converted_capitals,
        "converted_commutations": converted_commutations,
        "total_converted": total_converted,
        "skipped_zero_balance": skipped_accounts,
        "skipped_non_convertible": skipped_non_convertible if skipped_non_convertible else None,
        "converted_items": converted_items if converted_items else None,
        "skipped_items": skipped_items if skipped_items else None,
        "ignored_blocked_amount": blocked_field_amount if blocked_field_amount > 0 else None,
        "employer_current_severance_not_converted": employer_current_severance_total if employer_current_severance_total > 0 else None,
        "errors": errors if errors else None,
        "next_step": next_step,
        "source_data_cleared": source_data_cleared,
        "memory_cleared": memory_cleared,
        "persisted_source_scenarios_updated": scenarios_updated,
        "persisted_source_cleanup_ok": scenario_source_cleanup_ok,
        "source_pension_funds_zeroed": source_pension_funds_zeroed,
    }

    logger.info(
        "✅ TRANSFORM_FUNDS_TO_ASSETS completed: pensions=%d, capitals=%d, skipped=%d",
        converted_pensions,
        converted_capitals,
        skipped_accounts,
    )

    return response
