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
from .transform_funds_snapshot import execute_conversion_tasks
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

        from decimal import Decimal
        from datetime import date as date_type

        client_obj = getattr(agent_tools, "client", None)
        try:
            from app.services.retirement_age_service import DEFAULT_MALE_RETIREMENT_AGE

            retirement_age = int(DEFAULT_MALE_RETIREMENT_AGE)
        except Exception:
            retirement_age = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
        retirement_date: Optional[date] = None
        retirement_year = datetime.now().year
        if client_obj and getattr(client_obj, "birth_date", None) and getattr(client_obj, "gender", None):
            try:
                retirement_info = calculate_retirement_age(client_obj.birth_date, client_obj.gender)
                retirement_date = retirement_info.get("retirement_date")
                age_years = int(retirement_info.get("age_years") or retirement_age)
                age_months = int(retirement_info.get("age_months") or 0)
                retirement_age = age_years + (1 if age_months > 0 else 0)
                if retirement_date:
                    retirement_year = retirement_date.year
            except Exception as e:
                logger.warning(
                    "⚠️ Failed to calculate retirement age/date for client %s: %s",
                    client_id,
                    e,
                )

        # If the client is already past retirement age, execution defaults should reflect that.
        # We use today's date for pension start (unless overridden) and use the client's current age
        # to avoid falling back to a static retirement age in downstream coefficient logic.
        try:
            current_age = None
            if client_obj and hasattr(client_obj, "get_age"):
                current_age = client_obj.get_age()
            if current_age is not None and int(current_age) >= int(retirement_age):
                retirement_age = int(current_age)
                retirement_date = date_type.today()
                retirement_year = retirement_date.year
        except Exception:
            pass

        global_pension_start_date = _parse_date_value(pension_start_date_raw)

        converted_pensions = 0
        converted_capitals = 0
        skipped_accounts = 0
        errors = []

        source_pension_funds_zeroed = 0

        unresolved_severance_total = 0.0
        rights_sequence_total = 0.0
        blocked_field_amount = 0.0
        blocked_fields = {
            "פיצויים_שלא_עברו_התחשבנות",
            "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
        }
        employer_current_severance_total = 0.0
        for account in accounts:
            if not isinstance(account, dict):
                continue
            specific_amounts = account.get("specific_amounts")
            if isinstance(specific_amounts, dict) and specific_amounts:
                specific_amounts = _normalize_specific_amounts(specific_amounts)
            else:
                specific_amounts = _build_specific_amounts_from_account(account)

            raw_emp_current = specific_amounts.get("פיצויים_מעסיק_נוכחי", account.get("פיצויים_מעסיק_נוכחי"))
            try:
                emp_current_val = float(raw_emp_current or 0)
            except (TypeError, ValueError):
                emp_current_val = 0.0
            if emp_current_val > 0:
                employer_current_severance_total += emp_current_val

            if ignore_blocked_balances and specific_amounts:
                for bf in blocked_fields:
                    raw_val = specific_amounts.get(bf)
                    try:
                        val = float(raw_val or 0)
                    except (TypeError, ValueError):
                        val = 0.0
                    if val > 0:
                        specific_amounts.pop(bf, None)

            for key, target in (
                ("פיצויים_שלא_עברו_התחשבנות", "unresolved"),
                ("פיצויים_ממעסיקים_קודמים_רצף_זכויות", "rights"),
            ):
                raw_val = specific_amounts.get(key, account.get(key))
                try:
                    val = float(raw_val or 0)
                except (TypeError, ValueError):
                    val = 0.0
                if target == "unresolved":
                    unresolved_severance_total += val
                else:
                    rights_sequence_total += val

        if (unresolved_severance_total > 0 or rights_sequence_total > 0) and (not ignore_blocked_balances):
            ignore_blocked_balances = True

        conversion_tasks: list[dict] = []
        converted_items: list[dict] = []
        skipped_items: list[dict] = []

        validation_errors: list[str] = []

        skipped_non_convertible: list[dict[str, str]] = []

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
            return json.dumps(
                {
                    "success": False,
                    "error": "שגיאות ולידציה בהמרה",
                    "validation_errors": validation_errors,
                    "total_converted": 0,
                    "converted_pensions": 0,
                    "converted_capitals": 0,
                },
                ensure_ascii=False,
            )

        # Deterministic execution order: convert pensionable balances first, then capital assets.
        # This prevents regressions where capital conversions run before exhausting pension conversions
        # simply due to input account ordering.
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

        response = {
            "success": True,
            "message": f"✅ הומרו בהצלחה {total_converted} חשבונות: {converted_pensions} נכסי קצבה, {converted_capitals} נכסי הון.",
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
            "next_step": "כעת ניתן להפיק דוח באמצעות GENERATE_FULL_REPORT" if total_converted > 0 else None,
            "source_data_cleared": False,
            "memory_cleared": False,
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

        return json.dumps(response, ensure_ascii=False)

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
