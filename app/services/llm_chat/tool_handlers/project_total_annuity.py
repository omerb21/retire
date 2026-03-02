import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Client, PensionFund
from app.utils.date_serializer import parse_date_flexible

logger = logging.getLogger("app.llm_chat.tools")

try:
    from app.services.retirement_age_service import (
        DEFAULT_MALE_RETIREMENT_AGE as _DEFAULT_RETIREMENT_AGE_FALLBACK,
    )
except Exception:
    _DEFAULT_RETIREMENT_AGE_FALLBACK = 67


def handle_project_total_annuity(
    *,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
) -> str:
    logger.info("📊 PROJECT_TOTAL_ANNUITY called")

    try:
        from dateutil.relativedelta import relativedelta

        from app.services.annuity_coefficient import get_annuity_coefficient

        client_obj = db.query(Client).filter(Client.id == client_id).first()
        if not client_obj:
            return "Error: לקוח לא נמצא"

        retirement_age = args.get("retirement_age")
        retirement_age_val: int | None = None
        if retirement_age is not None:
            try:
                retirement_age_val = int(retirement_age)
            except Exception:
                retirement_age_val = None
        retirement_date_str = args.get("retirement_date")

        if retirement_date_str:
            retirement_date = parse_date_flexible(str(retirement_date_str))
        elif client_obj.birth_date and getattr(client_obj, "gender", None):
            try:
                from app.services.retirement_age_service import get_retirement_date

                if retirement_age_val is not None:
                    retirement_date = client_obj.birth_date + relativedelta(
                        years=retirement_age_val
                    )
                else:
                    retirement_date = get_retirement_date(
                        client_obj.birth_date, client_obj.gender
                    )
                    retirement_age_val = relativedelta(
                        retirement_date, client_obj.birth_date
                    ).years
            except Exception:
                if retirement_age_val is None:
                    try:
                        from app.services.retirement_age_service import (
                            get_retirement_age_simple,
                        )

                        retirement_age_val = int(
                            get_retirement_age_simple(
                                client_obj.birth_date, client_obj.gender
                            )
                        )
                    except Exception:
                        try:
                            from app.services.retirement_age_service import (
                                DEFAULT_MALE_RETIREMENT_AGE,
                            )

                            retirement_age_val = int(DEFAULT_MALE_RETIREMENT_AGE)
                        except Exception:
                            retirement_age_val = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
                retirement_date = client_obj.birth_date + relativedelta(
                    years=retirement_age_val
                )
        elif client_obj.birth_date:
            if retirement_age_val is None:
                try:
                    from app.services.retirement_age_service import (
                        get_retirement_age_simple,
                    )

                    retirement_age_val = int(
                        get_retirement_age_simple(
                            client_obj.birth_date,
                            getattr(client_obj, "gender", None) or "",
                        )
                    )
                except Exception:
                    try:
                        from app.services.retirement_age_service import (
                            DEFAULT_MALE_RETIREMENT_AGE,
                        )

                        retirement_age_val = int(DEFAULT_MALE_RETIREMENT_AGE)
                    except Exception:
                        retirement_age_val = int(_DEFAULT_RETIREMENT_AGE_FALLBACK)
            retirement_date = client_obj.birth_date + relativedelta(
                years=retirement_age_val
            )
        else:
            retirement_date = datetime.now().date() + relativedelta(years=10)

        logger.info(
            "📊 D10.1: Calculating total annuity for retirement date: %s",
            retirement_date,
        )

        total_monthly_annuity = 0.0
        total_balance = 0.0
        fund_details: list[dict[str, Any]] = []

        if pension_portfolio and len(pension_portfolio) > 0:
            logger.info(
                "📊 D10.2: Processing %s accounts from pension_portfolio (Maslaka)",
                len(pension_portfolio),
            )

            for account in pension_portfolio:
                if hasattr(account, "model_dump"):
                    acc_dict = account.model_dump()
                elif hasattr(account, "__dict__"):
                    acc_dict = vars(account)
                elif isinstance(account, dict):
                    acc_dict = account
                else:
                    logger.warning("D10.2: Unknown account type: %s", type(account))
                    continue

                balance = float(
                    acc_dict.get("יתרה", 0) or acc_dict.get("balance", 0) or 0
                )
                if balance <= 0:
                    continue

                total_balance += balance

                product_type = (
                    acc_dict.get("שם_מוצר", "")
                    or acc_dict.get("סוג_מוצר", "")
                    or "קרן פנסיה"
                )
                fund_name = (
                    acc_dict.get("שם_תכנית", "")
                    or acc_dict.get("fund_name", "")
                    or "ללא שם"
                )
                start_date_str = acc_dict.get("תאריך_התחלה", "")

                try:
                    start_date = retirement_date
                    if start_date_str:
                        try:
                            start_date = parse_date_flexible(str(start_date_str))
                        except Exception:
                            pass

                    coefficient_result = get_annuity_coefficient(
                        product_type=product_type,
                        start_date=start_date,
                        gender=client_obj.gender or "זכר",
                        retirement_age=retirement_age_val,
                        survivors_option="תקנוני",
                        spouse_age_diff=0,
                        birth_date=client_obj.birth_date,
                        pension_start_date=retirement_date,
                    )
                    annuity_factor = coefficient_result["factor_value"]
                    source = f"maslaka_{coefficient_result.get('source_table', 'calculated')}"
                except Exception as e:
                    logger.warning(
                        "D10.2: Coefficient error for %s: %s, using default 200",
                        fund_name,
                        e,
                    )
                    annuity_factor = 200
                    source = "maslaka_default"

                monthly_annuity = balance / annuity_factor
                total_monthly_annuity += monthly_annuity

                fund_details.append(
                    {
                        "fund_name": fund_name,
                        "product_type": product_type,
                        "balance": round(balance, 2),
                        "annuity_factor": round(float(annuity_factor), 2),
                        "monthly_annuity": round(monthly_annuity, 2),
                        "source": source,
                    }
                )

        pension_funds = (
            db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
        )
        logger.info("📊 D10.2: Found %s PensionFund records in DB", len(pension_funds))

        for fund in pension_funds:
            balance = float(fund.balance or 0)
            if balance <= 0:
                continue

            total_balance += balance

            if fund.annuity_factor and fund.annuity_factor > 0:
                annuity_factor = fund.annuity_factor
                source = "db_stored"
            else:
                try:
                    product_type = "קרן פנסיה"
                    if "ביטוח" in (fund.fund_name or ""):
                        product_type = "ביטוח מנהלים"
                    elif "קופת גמל" in (fund.fund_name or ""):
                        product_type = "קופת גמל"

                    coefficient_result = get_annuity_coefficient(
                        product_type=product_type,
                        start_date=fund.pension_start_date or retirement_date,
                        gender=client_obj.gender or "זכר",
                        retirement_age=retirement_age,
                        survivors_option="תקנוני",
                        spouse_age_diff=0,
                        birth_date=client_obj.birth_date,
                        pension_start_date=retirement_date,
                    )
                    annuity_factor = coefficient_result["factor_value"]
                    source = (
                        f"db_{coefficient_result.get('source_table', 'calculated')}"
                    )
                except Exception as e:
                    logger.warning(
                        "D10.2: Coefficient error for %s: %s, using default 200",
                        fund.fund_name,
                        e,
                    )
                    annuity_factor = 200
                    source = "db_default"

            monthly_annuity = balance / annuity_factor
            total_monthly_annuity += monthly_annuity

            fund_details.append(
                {
                    "fund_name": fund.fund_name,
                    "balance": round(balance, 2),
                    "annuity_factor": round(float(annuity_factor), 2),
                    "monthly_annuity": round(monthly_annuity, 2),
                    "source": source,
                }
            )

        response = {
            "success": True,
            "retirement_date": str(retirement_date),
            "retirement_age": retirement_age,
            "total_balance": round(total_balance, 2),
            "total_monthly_annuity": round(total_monthly_annuity, 2),
            "annual_annuity": round(total_monthly_annuity * 12, 2),
            "fund_count": len(fund_details),
            "fund_details": fund_details,
            "data_sources": {
                "maslaka_accounts": len(pension_portfolio) if pension_portfolio else 0,
                "db_pension_funds": len(pension_funds),
            },
        }

        logger.info(
            "📊 D10.1: Total annuity projection - balance: %s ₪, monthly: %s ₪",
            f"{total_balance:,.0f}",
            f"{total_monthly_annuity:,.0f}",
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("PROJECT_TOTAL_ANNUITY failed: %s", e, exc_info=True)
        return f"Error: שגיאה בחישוב הקצבה: {str(e)}"
