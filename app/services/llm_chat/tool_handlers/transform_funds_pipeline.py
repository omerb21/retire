from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import PensionFund
from app.models.capital_asset import CapitalAsset
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.pension_portfolio.conversion_rules import (
    is_education_fund,
    is_investment_provident_fund,
)
from app.services.retirement.utils.projection_utils import calculate_compound_factor

from .transform_funds_conversion import (
    _create_updated_snapshot_scenario,
    _delete_existing_tool_created_records,
    _derive_capital_tax_treatment_from_components,
    _parse_date_value,
    _zero_source_portfolio_pension_funds,
)
from .transform_funds_markers import build_transform_funds_response
from .transform_funds_validation import build_conversion_tasks_from_accounts
from .transform_funds_pipeline_parts.repository import (
    execute_conversion_tasks,
    apply_conversion_task_to_snapshot,
)

logger = logging.getLogger("app.llm_chat.tools")


def execute_transform_funds_pipeline(
    *,
    db,
    client_id,
    accounts,
    client_obj,
    global_pension_start_date,
    retirement_date,
    retirement_year,
    retirement_age,
    blocked_fields,
    ignore_blocked_balances,
    employer_current_severance_total: float,
    skip_non_convertible_accounts: bool,
    commute_pension_components: bool,
    default_conversion_type: str,
    remaining_only: bool,
    use_provided_accounts_only: bool,
) -> dict:
    conversion_tasks: list[dict] = []
    converted_items: list[dict] = []
    skipped_items: list[dict] = []

    validation_errors: list[str] = []

    skipped_non_convertible: list[dict[str, str]] = []

    converted_pensions = 0
    converted_capitals = 0
    skipped_accounts = 0
    errors = []

    source_pension_funds_zeroed = 0

    blocked_field_amount = 0.0

    (
        conversion_tasks,
        validation_errors,
        skipped_non_convertible,
        skipped_items,
        skipped_accounts,
        blocked_field_amount,
    ) = build_conversion_tasks_from_accounts(
        accounts=accounts,
        blocked_fields=blocked_fields,
        ignore_blocked_balances=ignore_blocked_balances,
        skip_non_convertible_accounts=skip_non_convertible_accounts,
        commute_pension_components=commute_pension_components,
        default_conversion_type=default_conversion_type,
        skipped_accounts=skipped_accounts,
        blocked_field_amount=blocked_field_amount,
    )

    if validation_errors:
        return {
            "success": False,
            "error": "שגיאות ולידציה בהמרה",
            "validation_errors": validation_errors,
            "total_converted": 0,
            "converted_pensions": 0,
            "converted_capitals": 0,
        }

    try:
        conversion_tasks.sort(
            key=lambda t: 0
            if str((t or {}).get("task_type") or "").lower() == "pension"
            else 1
        )
    except Exception:
        pass

    deleted_for_accounts: set[str] = set()
    source_zeroed_for_accounts: set[str] = set()
    snapshot_deltas: dict[str, dict] = {}
    converted_commutations = 0

    (
        skipped_accounts,
        snapshot_deltas,
        source_zeroed_for_accounts,
        source_pension_funds_zeroed,
        converted_pensions,
        converted_capitals,
        converted_commutations,
        converted_items,
        errors,
    ) = execute_conversion_tasks(
        conversion_tasks=conversion_tasks,
        remaining_only=remaining_only,
        db=db,
        client_id=client_id,
        global_pension_start_date=global_pension_start_date,
        retirement_date=retirement_date,
        retirement_year=retirement_year,
        retirement_age=retirement_age,
        use_provided_accounts_only=use_provided_accounts_only,
        client_obj=client_obj,
        deleted_for_accounts=deleted_for_accounts,
        source_zeroed_for_accounts=source_zeroed_for_accounts,
        snapshot_deltas=snapshot_deltas,
        source_pension_funds_zeroed=source_pension_funds_zeroed,
        converted_pensions=converted_pensions,
        converted_capitals=converted_capitals,
        converted_commutations=converted_commutations,
        converted_items=converted_items,
        skipped_accounts=skipped_accounts,
        errors=errors,
    )

    total_converted = converted_pensions + converted_capitals

    scenario_source_cleanup_ok = None
    scenarios_updated = 0

    try:
        scenario_source_cleanup_ok, scenarios_updated = _create_updated_snapshot_scenario(
            db=db,
            client_id=client_id,
            deltas=snapshot_deltas,
        )
    except Exception:
        scenario_source_cleanup_ok = False
        scenarios_updated = 0

    db.commit()

    try:
        db_url = str(db.get_bind().url)
    except Exception:
        db_url = None

    try:
        pf_count = (
            db.query(PensionFund)
            .filter(PensionFund.client_id == client_id)
            .count()
        )
        ca_count = (
            db.query(CapitalAsset)
            .filter(CapitalAsset.client_id == client_id)
            .count()
        )
        logger.info(
            "🔎 TRANSFORM_FUNDS_TO_ASSETS post-commit: client_id=%s db_url=%s pension_funds=%s capital_assets=%s",
            client_id,
            db_url,
            pf_count,
            ca_count,
        )
    except Exception as _count_err:
        logger.warning(
            "⚠️ TRANSFORM_FUNDS_TO_ASSETS post-commit count check failed: client_id=%s db_url=%s err=%s",
            client_id,
            db_url,
            _count_err,
        )

    response = build_transform_funds_response(
        success=True,
        message=f"✅ הומרו בהצלחה {total_converted} חשבונות: {converted_pensions} נכסי קצבה, {converted_capitals} נכסי הון.",
        converted_pensions=converted_pensions,
        converted_capitals=converted_capitals,
        converted_commutations=converted_commutations,
        total_converted=total_converted,
        skipped_accounts=skipped_accounts,
        skipped_non_convertible=skipped_non_convertible,
        converted_items=converted_items,
        skipped_items=skipped_items,
        blocked_field_amount=blocked_field_amount,
        employer_current_severance_total=employer_current_severance_total,
        errors=errors,
        next_step="כעת ניתן להפיק דוח באמצעות GENERATE_FULL_REPORT" if total_converted > 0 else None,
        source_data_cleared=False,
        memory_cleared=False,
        scenarios_updated=scenarios_updated,
        scenario_source_cleanup_ok=scenario_source_cleanup_ok,
        source_pension_funds_zeroed=source_pension_funds_zeroed,
    )

    return response


