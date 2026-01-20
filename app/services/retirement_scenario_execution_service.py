import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.fixation_result import FixationResult
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.routers.rights_fixation import (
    calculate_and_save_fixation_for_client,
    update_fixation_exempt_pension_fields,
)
from app.services.current_employer import EmploymentService as CurrentEmployerEmploymentService
from app.services.employment_service import EmploymentService as LegacyEmploymentService
from app.services.retirement import RetirementScenariosBuilder
from app.services.retirement.services.commutation_exemption_service import (
    CommutationExemptionService,
)

logger = logging.getLogger(__name__)


def _compute_snapshot_deltas_from_portfolio_pension_funds(
    *,
    db: Session,
    client_id: int,
) -> dict[str, dict]:
    deltas: dict[str, dict] = {}

    pension_funds = (
        db.query(PensionFund)
        .filter(PensionFund.client_id == client_id)
        .filter(PensionFund.conversion_source.isnot(None))
        .filter(PensionFund.conversion_source.like('%%"source": "pension_portfolio"%%'))
        .all()
    )

    for pf in pension_funds:
        raw_source = getattr(pf, "conversion_source", None)
        if not raw_source:
            continue

        try:
            source_data = json.loads(raw_source)
        except Exception:
            continue
        if not isinstance(source_data, dict):
            continue

        account_number = (
            (source_data.get("account_number") or source_data.get("account") or source_data.get("accountNo"))
            or getattr(pf, "deduction_file", None)
        )
        if not account_number:
            continue
        account_number = str(account_number).strip()
        if not account_number:
            continue

        original_balance = source_data.get("original_balance") or source_data.get("amount")
        try:
            original_total = float(original_balance or 0)
        except (TypeError, ValueError):
            original_total = 0.0

        try:
            current_total = float(getattr(pf, "balance", None) or 0)
        except (TypeError, ValueError):
            current_total = 0.0

        if original_total <= 0:
            continue

        delta_total = max(0.0, original_total - current_total)
        if delta_total <= 0.01:
            continue

        entry = deltas.setdefault(account_number, {"total": 0.0, "fields": {}})
        entry["total"] = float(entry.get("total") or 0.0) + float(delta_total)

        specific_amounts = source_data.get("specific_amounts")
        if isinstance(specific_amounts, dict) and specific_amounts:
            ratio = 0.0
            try:
                ratio = delta_total / original_total
            except Exception:
                ratio = 0.0
            fields = entry.get("fields")
            if not isinstance(fields, dict):
                fields = {}

            for k, v in specific_amounts.items():
                try:
                    numeric = float(v or 0)
                except (TypeError, ValueError):
                    numeric = 0.0
                if numeric <= 0:
                    continue
                fields[str(k)] = float(fields.get(str(k), 0.0)) + (numeric * ratio)

            entry["fields"] = fields

        deltas[account_number] = entry

    return deltas


def execute_retirement_scenario(db: Session, client_id: int, scenario_id: int) -> dict:
    logger.info("⚡ Executing scenario %s for client %s", scenario_id, client_id)

    db_client = db.query(Client).filter(Client.id == client_id).first()
    if not db_client:
        raise ValueError("client_not_found")

    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.client_id == client_id)
        .first()
    )
    if not scenario:
        raise ValueError("scenario_not_found")

    try:
        params = json.loads(scenario.parameters) if scenario.parameters else {}
        retirement_age = params.get("retirement_age")
        scenario_type = params.get("scenario_type")
        include_current_employer_termination = bool(
            params.get("include_current_employer_termination") or False
        )

        if not retirement_age:
            raise ValueError("גיל פרישה חסר בתרחיש")

        logger.info("🧹 Step 1: Cleaning up previous scenario results...")

        cleanup_count = 0

        deleted_fixations = (
            db.query(FixationResult)
            .filter(FixationResult.client_id == client_id)
            .delete(synchronize_session=False)
        )
        cleanup_count += deleted_fixations

        scenario_pensions = (
            db.query(PensionFund)
            .filter(
                PensionFund.client_id == client_id,
                PensionFund.conversion_source.isnot(None),
                PensionFund.conversion_source.like('%"source": "termination_event"%'),
            )
            .all()
        )

        for pf in scenario_pensions:
            logger.info("  🗑️ Deleting scenario pension: %s", pf.fund_name)
            db.delete(pf)
            cleanup_count += 1

        portfolio_pensions = (
            db.query(PensionFund)
            .filter(
                PensionFund.client_id == client_id,
                PensionFund.conversion_source.isnot(None),
                PensionFund.conversion_source.like('%"source": "pension_portfolio"%'),
            )
            .all()
        )

        for pf in portfolio_pensions:
            if pf.pension_amount:
                logger.info(
                    "  🔄 Resetting pension_amount for: %s (keeping balance)",
                    pf.fund_name,
                )
                try:
                    if pf.balance is None and pf.conversion_source:
                        source_data = json.loads(pf.conversion_source)
                        if isinstance(source_data, dict):
                            original_balance = source_data.get("original_balance") or source_data.get(
                                "amount"
                            )
                            if original_balance is not None:
                                pf.balance = float(original_balance)
                                logger.info(
                                    "    🔁 Restored original balance for %s from conversion_source: %.2f",
                                    pf.fund_name,
                                    pf.balance,
                                )
                except Exception as e:
                    logger.warning(
                        "  ⚠️ Failed to restore original balance for %s: %s",
                        pf.fund_name,
                        e,
                    )

                pf.pension_amount = None
                pf.pension_start_date = None
                cleanup_count += 1

        scenario_capital = (
            db.query(CapitalAsset)
            .filter(
                CapitalAsset.client_id == client_id,
                CapitalAsset.conversion_source.isnot(None),
            )
            .all()
        )

        for ca in scenario_capital:
            logger.info("  🗑️ Deleting scenario capital: %s", ca.asset_name)
            db.delete(ca)
            cleanup_count += 1

        scenario_incomes = (
            db.query(AdditionalIncome)
            .filter(
                AdditionalIncome.client_id == client_id,
                AdditionalIncome.remarks.isnot(None),
                AdditionalIncome.remarks.like('%"source": "scenario_conversion"%'),
            )
            .all()
        )

        for ai in scenario_incomes:
            logger.info("  🗑️ Deleting scenario income: %s", ai.description)
            db.delete(ai)
            cleanup_count += 1

        db.flush()
        logger.info("  ✅ Cleaned up %s items from previous scenarios", cleanup_count)
        logger.info("")

        logger.info("⚡ Step 2: Executing new scenario...")

        pension_portfolio_data = params.get("pension_portfolio")

        if not pension_portfolio_data:
            logger.warning("  ⚠️ No pension portfolio data found in saved scenario")
        else:
            logger.info(
                "  📦 Found %s pension accounts in saved scenario",
                len(pension_portfolio_data),
            )

        builder = RetirementScenariosBuilder(
            db,
            client_id,
            retirement_age,
            pension_portfolio_data,
            use_current_employer_termination=include_current_employer_termination,
        )

        if scenario_type == "scenario_1_max_pension":
            result = builder._build_max_pension_scenario()
        elif scenario_type == "scenario_2_max_capital":
            result = builder._build_max_capital_scenario()
        elif scenario_type == "scenario_3_max_npv":
            result = builder._build_max_npv_scenario()
        else:
            raise ValueError(f"סוג תרחיש לא ידוע: {scenario_type}")

        try:
            from app.services.llm_chat.tool_handlers.transform_funds_conversion import (
                _create_updated_snapshot_scenario,
            )

            deltas = _compute_snapshot_deltas_from_portfolio_pension_funds(
                db=db,
                client_id=client_id,
            )
            if deltas:
                _create_updated_snapshot_scenario(
                    db=db,
                    client_id=client_id,
                    deltas=deltas,
                )
        except Exception:
            pass

        if include_current_employer_termination:
            try:
                if db_client and db_client.birth_date and retirement_age:
                    retirement_year_for_termination = db_client.birth_date.year + int(
                        retirement_age
                    )
                    actual_termination_date = date(retirement_year_for_termination, 1, 1)

                    try:
                        termination_event = LegacyEmploymentService.confirm_termination(
                            db=db,
                            client_id=client_id,
                            actual_date=actual_termination_date,
                        )
                        logger.info(
                            "  ✅ Employment termination confirmed during scenario execution (termination_event_id=%s, date=%s)",
                            getattr(termination_event, "id", None),
                            actual_termination_date.isoformat(),
                        )
                    except ValueError as e:
                        logger.info(
                            "  ℹ️ Skipping legacy Employment termination confirmation (business rule): %s",
                            str(e),
                        )
                    except Exception as e:
                        logger.error(
                            "  ⚠️ Failed to confirm legacy Employment termination during scenario execution: %s",
                            str(e),
                        )

                    try:
                        ce_service = CurrentEmployerEmploymentService(db)
                        current_employer = ce_service.get_employer(client_id)
                        ce_service.update_employer_end_date(
                            current_employer, actual_termination_date
                        )
                        logger.info(
                            "  ✅ CurrentEmployer end_date updated during scenario execution (employer_id=%s, date=%s)",
                            getattr(current_employer, "id", None),
                            actual_termination_date.isoformat(),
                        )
                    except ValueError as e:
                        logger.info(
                            "  ℹ️ Skipping CurrentEmployer termination update: %s",
                            str(e),
                        )
                    except Exception as e:
                        logger.error(
                            "  ⚠️ Failed to update CurrentEmployer termination during scenario execution: %s",
                            str(e),
                        )
                else:
                    logger.info(
                        "  ℹ️ Skipping employment termination confirmation: missing birth_date or retirement_age"
                    )
            except Exception as e:
                logger.error(
                    "  ⚠️ Unexpected error during employment termination handling in scenario execution: %s",
                    str(e),
                )
        else:
            logger.info(
                "  ℹ️ Skipping employment termination handling during scenario execution (include_current_employer_termination=False)"
            )

        fixation_record = None
        try:
            fixation_record = calculate_and_save_fixation_for_client(db, client_id)
            if fixation_record:
                logger.info(
                    "  ✅ Auto rights fixation saved during scenario execution (fixation_id=%s)",
                    fixation_record.id,
                )
            else:
                logger.info(
                    "  ℹ️ Auto rights fixation skipped (client not eligible or no grants)"
                )
        except Exception as fixation_error:
            logger.error(
                "  ⚠️ Failed to auto-calculate rights fixation: %s", fixation_error
            )

        if scenario_type == "scenario_2_max_capital" and fixation_record is not None:
            try:
                commutation_service = CommutationExemptionService(db, client_id)
                commutation_service.apply_exempt_capital_to_scenario_commutations(
                    fixation_record
                )
            except Exception as e:
                logger.error(
                    "  ⚠️ Failed to apply exempt capital to scenario commutations or calculate NPV effect: %s",
                    e,
                )

        if fixation_record is not None:
            try:
                update_fixation_exempt_pension_fields(fixation_record)
            except Exception as e:
                logger.error(
                    "  ⚠️ Failed to update exempt pension fields on fixation result: %s",
                    e,
                )

        db.commit()

        actions_count = len(result.get("execution_plan", []))

        logger.info("")
        logger.info("✅ Scenario %s executed successfully!", scenario_id)
        logger.info("   - Cleaned: %s old items", cleanup_count)
        logger.info("   - Actions: %s steps", actions_count)
        logger.info(
            "   - Pension: %.0f ₪/month", result.get("total_pension_monthly", 0)
        )
        logger.info(
            "   - Capital: %s ₪",
            f"{float(result.get('total_capital', 0) or 0):,.0f}",
        )

        return {
            "success": True,
            "message": f"התרחיש בוצע בהצלחה (ניקוי: {cleanup_count} פריטים, פעולות: {actions_count})",
            "scenario_id": scenario_id,
            "scenario_name": scenario.scenario_name,
            "cleanup_count": cleanup_count,
            "actions_count": actions_count,
            "result": result,
            "include_current_employer_termination": include_current_employer_termination,
        }

    except Exception:
        db.rollback()
        raise
