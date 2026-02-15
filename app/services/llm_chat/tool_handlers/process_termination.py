import json
import logging
from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Client, CurrentEmployer
from app.utils.date_serializer import parse_date_flexible

logger = logging.getLogger("app.llm_chat.tools")


def handle_process_termination(
    *,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
) -> str:
    logger.info("🔴 PROCESS_TERMINATION called - Execution Mode!")

    if not isinstance(args, dict):
        return "Error: arguments חייב להיות אובייקט (dict)"

    # Contract: the agent should send only confirmed + exempt_choice + taxable_choice
    # (optional use_employer_completion=true). Amounts and dates are completed server-side.

    try:
        if isinstance(args.get("exempt_choice"), str):
            raw_exempt_choice = args.get("exempt_choice").strip().lower()
            if raw_exempt_choice in {"capital", "lump_sum", "lumpsum", "one_time", "one-time"}:
                args["exempt_choice"] = "redeem_with_exemption"
            elif raw_exempt_choice in {"pension", "annuity"}:
                args["exempt_choice"] = "annuity"
        if isinstance(args.get("taxable_choice"), str):
            raw_taxable_choice = args.get("taxable_choice").strip().lower()
            if raw_taxable_choice in {"capital", "lump_sum", "lumpsum", "one_time", "one-time"}:
                args["taxable_choice"] = "redeem_no_exemption"
            elif raw_taxable_choice in {"pension", "annuity"}:
                args["taxable_choice"] = "annuity"
    except Exception:
        pass

    if args.get("exempt_choice") is None:
        args["exempt_choice"] = "redeem_with_exemption"
    if args.get("taxable_choice") is None:
        args["taxable_choice"] = "annuity"

    required_params = [
        "exempt_choice",
        "taxable_choice",
        "confirmed",
    ]
    missing = [p for p in required_params if args.get(p) is None]
    if missing:
        return (
            "Error: חסרים פרמטרים לביצוע עזיבת עבודה: "
            + ", ".join(missing)
            + "."
        )

    if not args.get("confirmed"):
        return "Error: הפעולה לא אושרה. יש להגדיר confirmed=true לביצוע עזיבת עבודה."

    try:
        from app.schemas.current_employer import TerminationDecisionCreate
        from app.services.current_employer import TerminationService

        client_obj = db.query(Client).filter(Client.id == client_id).first()
        if not client_obj:
            return "Error: לקוח לא נמצא"

        employer = (
            db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == client_id)
            .first()
        )
        if not employer:
            return "Error: מעסיק נוכחי לא נמצא"

        termination_date_str = args.get("termination_date")
        termination_date = (
            parse_date_flexible(str(termination_date_str))
            if termination_date_str is not None and str(termination_date_str).strip()
            else None
        )

        plan_details_str = args.get("plan_details")
        if not plan_details_str and pension_portfolio:
            plan_details_list = []

            for account in pension_portfolio:
                if hasattr(account, "model_dump"):
                    acc_dict = account.model_dump()
                elif hasattr(account, "__dict__"):
                    acc_dict = vars(account)
                elif isinstance(account, dict):
                    acc_dict = account
                else:
                    logger.warning("D3.10: Unknown account type: %s", type(account))
                    continue

                severance_amount = float(acc_dict.get("פיצויים_מעסיק_נוכחי", 0) or 0)
                if severance_amount > 0:
                    plan_detail = {
                        "plan_name": acc_dict.get("שם_תכנית", "ללא שם"),
                        "plan_start_date": acc_dict.get("תאריך_התחלה"),
                        "product_type": acc_dict.get(
                            "סוג_מוצר",
                            acc_dict.get("שם_מוצר", "קופת גמל"),
                        ),
                        "amount": severance_amount,
                    }
                    plan_details_list.append(plan_detail)
                    logger.info(
                        "📋 D3.9: Added plan from portfolio: %s (%s) - %s ₪",
                        plan_detail["plan_name"],
                        plan_detail["product_type"],
                        f"{severance_amount:,.0f}",
                    )

            if plan_details_list:
                plan_details_str = json.dumps(plan_details_list, ensure_ascii=False)
                logger.info(
                    "📋 D3.9: Built plan_details from portfolio: %s plans",
                    len(plan_details_list),
                )

        taxable_annuity_amount = args.get("taxable_annuity_amount")
        taxable_capital_amount = args.get("taxable_capital_amount")
        taxable_amount = float(args.get("taxable_amount")) if args.get("taxable_amount") is not None else None

        if taxable_annuity_amount is not None or taxable_capital_amount is not None:
            taxable_annuity_amount = float(taxable_annuity_amount or 0)
            taxable_capital_amount = float(taxable_capital_amount or 0)
            total_split = taxable_annuity_amount + taxable_capital_amount

            if taxable_amount is not None and total_split > taxable_amount + 0.01:
                return (
                    f"Error: סכום הפיצול ({total_split:,.0f} ₪) גדול מהסכום החייב ({taxable_amount:,.0f} ₪)"
                )

            logger.info(
                "📊 D4.1: Split taxable amount - annuity: %s, capital: %s",
                f"{taxable_annuity_amount:,.0f}",
                f"{taxable_capital_amount:,.0f}",
            )

        decision = TerminationDecisionCreate(
            termination_date=termination_date,
            use_employer_completion=args.get("use_employer_completion", True),
            severance_amount=float(args.get("severance_amount")) if args.get("severance_amount") is not None else None,
            exempt_amount=float(args.get("exempt_amount")) if args.get("exempt_amount") is not None else None,
            taxable_amount=taxable_amount,
            exempt_choice=args.get("exempt_choice"),
            taxable_choice=args.get("taxable_choice"),
            taxable_annuity_amount=taxable_annuity_amount if taxable_annuity_amount else None,
            taxable_capital_amount=taxable_capital_amount if taxable_capital_amount else None,
            tax_spread_years=args.get("tax_spread_years"),
            plan_details=plan_details_str,
            confirmed=True,
        )

        termination_service = TerminationService(db)
        result = termination_service.process_termination(client_obj, employer, decision)

        logger.info("✅ PROCESS_TERMINATION completed: %s", result)

        response = {
            "success": True,
            "message": "הפעולה בוצעה בהצלחה!",
            "created_grant_id": result.get("created_grant_id"),
            "created_pension_id": result.get("created_pension_id"),
            "created_capital_asset_id": result.get("created_capital_asset_id"),
            "employment_years": result.get("employment_years"),
            "max_spread_years": result.get("max_spread_years"),
            "details": {
                "termination_date": termination_date_str,
                "severance_amount": args.get("severance_amount"),
                "exempt_amount": args.get("exempt_amount"),
                "taxable_amount": args.get("taxable_amount"),
                "exempt_choice": args.get("exempt_choice"),
                "taxable_choice": args.get("taxable_choice"),
                "taxable_annuity_amount": args.get("taxable_annuity_amount"),
                "taxable_capital_amount": args.get("taxable_capital_amount"),
            },
        }

        logger.info(
            "📊 D4.3: Employment years: %s, Max spread: %s",
            result.get("employment_years"),
            result.get("max_spread_years"),
        )

        if result.get("effective_spread_years"):
            response["effective_spread_years"] = result.get("effective_spread_years")
            response["requested_spread_years"] = result.get("requested_spread_years")
            logger.info(
                "📊 D4.4: Spread years - requested: %s, effective: %s",
                result.get("requested_spread_years"),
                result.get("effective_spread_years"),
            )

        capital_tax_info = result.get("capital_tax_info")
        if capital_tax_info:
            response["capital_tax_info"] = capital_tax_info
            logger.info(
                "💰 D4.2: Adding tax info to response - total_tax: %s, net: %s",
                f"{capital_tax_info.get('total_tax', 0):,.0f}",
                f"{capital_tax_info.get('net_amount', 0):,.0f}",
            )

        annuity_projection = result.get("annuity_projection")
        if annuity_projection:
            response["annuity_projection"] = annuity_projection
            logger.info(
                "📊 D6.1: Annuity projection - deposit: %s ₪, monthly: %s ₪",
                f"{annuity_projection.get('total_annuity_deposit', 0):,.0f}",
                f"{annuity_projection.get('total_monthly_annuity', 0):,.0f}",
            )

        severance_reset_info = result.get("severance_reset_info", {})
        if severance_reset_info.get("portfolio_severance_to_reset"):
            response["severance_cleanup"] = {
                "severance_reset_completed": True,
                "original_severance_amount": severance_reset_info.get(
                    "employer_severance_accrued_reset", 0
                ),
                "source_accounts": severance_reset_info.get("source_accounts", []),
            }
            logger.info(
                "🔄 D9.1: Severance cleanup confirmed - original: %s ₪",
                f"{severance_reset_info.get('employer_severance_accrued_reset', 0):,.0f}",
            )

            reset_marker = (
                "###SEVERANCE_RESET###"
                + json.dumps(severance_reset_info, ensure_ascii=False)
                + "###END_SEVERANCE_RESET###"
            )
            return json.dumps(response, ensure_ascii=False) + reset_marker

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("PROCESS_TERMINATION failed: %s", e, exc_info=True)
        return f"Error: שגיאה בביצוע הפעולה: {str(e)}"
