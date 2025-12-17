import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import PensionFund

logger = logging.getLogger("app.llm_chat.tools")


def handle_get_account_details(
    *,
    args: dict,
    client_id: int,
    db: Session,
    pension_portfolio: Optional[list[Any]] = None,
) -> str:
    logger.info("🔍 GET_ACCOUNT_DETAILS called")

    try:
        search_term = str(args.get("search_term", "")).strip().lower()
        if not search_term:
            return "Error: חסר פרמטר search_term"

        logger.info("🔍 D11.1: Searching for accounts matching: '%s'", search_term)

        matching_accounts: list[dict[str, Any]] = []

        if pension_portfolio and len(pension_portfolio) > 0:
            logger.info(
                "🔍 D11.1: Searching in %s Maslaka accounts",
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
                    continue

                fund_name = str(acc_dict.get("שם_תכנית", "") or "").lower()
                company_name = str(
                    acc_dict.get("חברה_מנהלת", "")
                    or acc_dict.get("שם_חברה", "")
                    or ""
                ).lower()
                product_type = str(
                    acc_dict.get("סוג_מוצר", "")
                    or acc_dict.get("שם_מוצר", "")
                    or ""
                ).lower()

                if (
                    search_term in fund_name
                    or search_term in company_name
                    or search_term in product_type
                ):
                    balance = float(acc_dict.get("יתרה", 0) or 0)
                    severance_current = float(acc_dict.get("פיצויים_מעסיק_נוכחי", 0) or 0)
                    severance_after_settlement = float(
                        acc_dict.get("פיצויים_לאחר_התחשבנות", 0) or 0
                    )
                    severance_not_settled = float(
                        acc_dict.get("פיצויים_שלא_עברו_התחשבנות", 0) or 0
                    )
                    severance_prev_rights = float(
                        acc_dict.get("פיצויים_ממעסיקים_קודמים_רצף_זכויות", 0) or 0
                    )
                    severance_prev_pension = float(
                        acc_dict.get("פיצויים_ממעסיקים_קודמים_רצף_קצבה", 0) or 0
                    )
                    tagmulim = float(
                        acc_dict.get("תגמולים", 0)
                        or acc_dict.get("סך_תגמולים", 0)
                        or 0
                    )

                    is_sequence_of_rights = severance_prev_rights > 0

                    account_details = {
                        "fund_name": acc_dict.get("שם_תכנית", "ללא שם"),
                        "company_name": acc_dict.get("חברה_מנהלת", "")
                        or acc_dict.get("שם_חברה", "לא ידוע"),
                        "product_type": acc_dict.get("סוג_מוצר", "")
                        or acc_dict.get("שם_מוצר", "לא ידוע"),
                        "current_balance": round(balance, 2),
                        "severance_current_employer": round(severance_current, 2),
                        "severance_past_employers": round(severance_prev_pension, 2),
                        "severance_past_employers_sequence_rights": round(
                            severance_prev_rights, 2
                        ),
                        "severance_after_settlement": round(severance_after_settlement, 2),
                        "severance_not_settled": round(severance_not_settled, 2),
                        "tagmulim": round(tagmulim, 2),
                        "is_in_sequence_of_rights": is_sequence_of_rights,
                        "start_date": acc_dict.get("תאריך_התחלה", None),
                        "source": "maslaka",
                    }
                    matching_accounts.append(account_details)

        pension_funds = db.query(PensionFund).filter(PensionFund.client_id == client_id).all()
        logger.info(
            "🔍 D11.1: Searching in %s DB PensionFund records",
            len(pension_funds),
        )

        for fund in pension_funds:
            fund_name_lower = (fund.fund_name or "").lower()

            if search_term in fund_name_lower:
                balance = float(fund.balance or 0)

                account_details = {
                    "fund_name": fund.fund_name,
                    "company_name": "מ-DB",
                    "product_type": fund.fund_type or "לא ידוע",
                    "current_balance": round(balance, 2),
                    "annuity_factor": fund.annuity_factor,
                    "pension_amount": round(float(fund.pension_amount or 0), 2),
                    "pension_start_date": str(fund.pension_start_date)
                    if fund.pension_start_date
                    else None,
                    "tax_treatment": fund.tax_treatment,
                    "is_in_sequence_of_rights": False,
                    "source": "db",
                }
                matching_accounts.append(account_details)

        response = {
            "success": True,
            "search_term": search_term,
            "matches_found": len(matching_accounts),
            "accounts": matching_accounts,
        }

        if len(matching_accounts) == 0:
            response["message"] = f"לא נמצאו חשבונות התואמים לחיפוש '{search_term}'"
            logger.info("🔍 D11.1: No matches found for '%s'", search_term)
        else:
            logger.info("🔍 D11.1: Found %s matching accounts", len(matching_accounts))

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("GET_ACCOUNT_DETAILS failed: %s", e, exc_info=True)
        return f"Error: שגיאה בחיפוש חשבון: {str(e)}"
