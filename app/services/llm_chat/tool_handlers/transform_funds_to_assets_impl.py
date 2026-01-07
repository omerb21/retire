import json
import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import PensionFund, Scenario
from app.models.capital_asset import CapitalAsset
from app.services.annuity_coefficient import get_annuity_coefficient
from app.services.llm_agent_tools_service import AgentToolsService
from app.services.llm_chat.orchestration_utils import build_transform_accounts_from_portfolio
from app.services.pension_portfolio.conversion_rules import (
    is_education_fund,
    is_investment_provident_fund,
    preferred_conversion_type_for_component,
    validate_component_conversion,
)
from app.services.llm_chat.portfolio_context import _is_education_fund
from app.services.retirement.utils.projection_utils import calculate_compound_factor
from app.services.retirement_age_service import calculate_retirement_age

from .transform_funds_classification import classify_product_type
from .transform_funds_conversion import (
    _apply_snapshot_deltas,
    _build_specific_amounts_from_account,
    _coerce_float,
    _create_updated_snapshot_scenario,
    _delete_existing_tool_created_records,
    _derive_capital_tax_treatment_from_components,
    _derive_conversion_type_from_components,
    _is_allowed_capital_without_breakdown,
    _normalize_specific_amounts,
    _parse_date_value,
    _preferred_conversion_type_for_component,
    _validate_component_conversion,
    _zero_source_portfolio_pension_funds,
)
from .transform_funds_snapshot import run_transform_funds_execution_window
from .transform_funds_validation import build_conversion_tasks_from_accounts

logger = logging.getLogger("app.llm_chat.tools")

try:
    from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67


def handle_transform_funds_to_assets(
    *,
    args: dict,
    client_id: int,
    db: Session,
    agent_tools: AgentToolsService,
) -> str:
    logger.info("🔄 TRANSFORM_FUNDS_TO_ASSETS called - Converting funds to assets")

    try:
        accounts = args.get("accounts", [])
        remaining_only = bool(args.get("remaining_only"))
        pension_start_date_raw = args.get("pension_start_date")
        default_conversion_type = args.get("default_conversion_type", "pension")
        commute_pension_components_raw = args.get("commute_pension_components")
        commute_pension_components = bool(commute_pension_components_raw) if commute_pension_components_raw is not None else False
        ignore_blocked_balances_raw = args.get("ignore_blocked_balances")
        ignore_blocked_balances = (
            True if ignore_blocked_balances_raw is None else bool(ignore_blocked_balances_raw)
        )
        skip_non_convertible_accounts_raw = args.get("skip_non_convertible_accounts")
        skip_non_convertible_accounts = (
            True
            if skip_non_convertible_accounts_raw is None
            else bool(skip_non_convertible_accounts_raw)
        )
        use_provided_accounts_only = bool(args.get("use_provided_accounts_only"))
        try:
            if isinstance(accounts, list) and any(
                isinstance(a, dict) and bool(a.get("_partial_conversion")) for a in accounts
            ):
                use_provided_accounts_only = True
        except Exception:
            pass

        def _is_aggregate_account(acc: dict) -> bool:
            name = str(acc.get("account_name") or acc.get("שם_תכנית") or "")
            number = str(
                acc.get("account_number")
                or acc.get("מספר_חשבון")
                or acc.get("מספר חשבון")
                or acc.get("מספר-חשבון")
                or ""
            )
            product_type = str(acc.get("product_type") or acc.get("סוג_מוצר") or "")
            return (
                name.startswith("Aggregate_")
                or number.startswith("AGG-")
                or product_type.startswith("aggregate_")
            )

        portfolio = getattr(agent_tools, "pension_portfolio_data", None)
        derived_accounts = build_transform_accounts_from_portfolio(portfolio)

        if (not use_provided_accounts_only) and derived_accounts:
            provided_numbers = {
                str(
                    a.get("account_number")
                    or a.get("מספר_חשבון")
                    or a.get("מספר חשבון")
                    or a.get("מספר-חשבון")
                    or ""
                ).strip()
                for a in accounts
                if isinstance(a, dict)
            }
            derived_numbers = {
                str(
                    a.get("account_number")
                    or a.get("מספר_חשבון")
                    or a.get("מספר חשבון")
                    or a.get("מספר-חשבון")
                    or ""
                ).strip()
                for a in derived_accounts
                if isinstance(a, dict)
            }
            provided_numbers.discard("")
            derived_numbers.discard("")

            should_replace = (not accounts) or (len(derived_accounts) > len(accounts))
            if derived_numbers and provided_numbers and not derived_numbers.issubset(provided_numbers):
                should_replace = True

            if should_replace:
                logger.info(
                    "🔁 Using derived portfolio accounts for transform (client_id=%s, provided=%s, derived=%s)",
                    client_id,
                    len(accounts) if isinstance(accounts, list) else 0,
                    len(derived_accounts),
                )
                accounts = derived_accounts

        if (not use_provided_accounts_only) and isinstance(accounts, list) and accounts:
            if any(_is_aggregate_account(a) for a in accounts if isinstance(a, dict)):
                if derived_accounts:
                    logger.info(
                        "🔁 Replacing aggregate accounts with derived portfolio accounts (client_id=%s, aggregates=%s, derived=%s)",
                        client_id,
                        len([a for a in accounts if isinstance(a, dict) and _is_aggregate_account(a)]),
                        len(derived_accounts),
                    )
                    accounts = derived_accounts

        if not accounts or not isinstance(accounts, list):
            return json.dumps(
                {
                    "success": False,
                    "error": "חסרה רשימת חשבונות להמרה (accounts)",
                    "total_converted": 0,
                    "converted_pensions": 0,
                    "converted_capitals": 0,
                },
                ensure_ascii=False,
            )

        return run_transform_funds_execution_window(
            client_id=client_id,
            db=db,
            agent_tools=agent_tools,
            accounts=accounts,
            pension_start_date_raw=pension_start_date_raw,
            ignore_blocked_balances=ignore_blocked_balances,
            skip_non_convertible_accounts=skip_non_convertible_accounts,
            commute_pension_components=commute_pension_components,
            default_conversion_type=default_conversion_type,
            remaining_only=remaining_only,
            use_provided_accounts_only=use_provided_accounts_only,
            default_retirement_age_fallback=_DEFAULT_RETIREMENT_AGE_FALLBACK,
        )

    except Exception as e:
        logger.error("TRANSFORM_FUNDS_TO_ASSETS failed: %s", e, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "error": f"שגיאה בהמרת הכספים: {str(e)}",
                "total_converted": 0,
                "converted_pensions": 0,
                "converted_capitals": 0,
            },
            ensure_ascii=False,
        )
