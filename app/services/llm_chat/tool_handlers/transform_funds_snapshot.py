from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .transform_funds_context import prepare_transform_funds_context
from .transform_funds_pipeline import execute_transform_funds_pipeline

logger = logging.getLogger("app.llm_chat.tools")


def run_transform_funds_execution_window(
    *,
    client_id: int,
    db: Session,
    agent_tools,
    accounts: list,
    execution_plan: dict | None,
    pension_start_date_raw,
    ignore_blocked_balances: bool,
    skip_non_convertible_accounts: bool,
    commute_pension_components: bool,
    default_conversion_type: str,
    remaining_only: bool,
    use_provided_accounts_only: bool,
    _DEFAULT_RETIREMENT_AGE_FALLBACK: int,
) -> dict:
    ctx = prepare_transform_funds_context(
        client_id=client_id,
        agent_tools=agent_tools,
        accounts=accounts,
        pension_start_date_raw=pension_start_date_raw,
        ignore_blocked_balances=ignore_blocked_balances,
        _DEFAULT_RETIREMENT_AGE_FALLBACK=_DEFAULT_RETIREMENT_AGE_FALLBACK,
    )

    response = execute_transform_funds_pipeline(
        db=db,
        client_id=client_id,
        accounts=accounts,
        execution_plan=execution_plan,
        client_obj=ctx.get("client_obj"),
        global_pension_start_date=ctx.get("global_pension_start_date"),
        retirement_date=ctx.get("retirement_date"),
        retirement_year=ctx.get("retirement_year"),
        retirement_age=ctx.get("retirement_age"),
        blocked_fields=ctx.get("blocked_fields"),
        ignore_blocked_balances=ctx.get("ignore_blocked_balances"),
        employer_current_severance_total=ctx.get("employer_current_severance_total"),
        skip_non_convertible_accounts=skip_non_convertible_accounts,
        commute_pension_components=commute_pension_components,
        default_conversion_type=default_conversion_type,
        remaining_only=remaining_only,
        use_provided_accounts_only=use_provided_accounts_only,
    )

    return response
