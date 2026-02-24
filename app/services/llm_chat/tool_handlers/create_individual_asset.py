import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import PensionFund
from app.models.capital_asset import CapitalAsset

logger = logging.getLogger("app.llm_chat.tools")


def handle_create_individual_asset(*, args: dict, client_id: int, db: Session) -> str:
    logger.info("🏦 CREATE_INDIVIDUAL_ASSET called - Creating individual asset")

    try:
        asset_category = args.get("asset_category")
        asset_name = args.get("asset_name")
        asset_type = args.get("asset_type")
        balance = args.get("balance")
        monthly_amount = args.get("monthly_amount")
        start_date_str = args.get("start_date")
        tax_treatment = args.get("tax_treatment", "taxable")
        annuity_factor = args.get("annuity_factor")

        if not asset_category:
            return "Error: חסרה קטגוריית נכס (asset_category)"
        if not asset_name:
            return "Error: חסר שם נכס (asset_name)"
        if balance is None:
            return "Error: חסרה יתרה (balance)"
        if not start_date_str:
            return "Error: חסר תאריך התחלה (start_date)"

        from decimal import Decimal

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        if asset_category == "pension":
            fund_type = asset_type or "קרן פנסיה"
            factor = float(annuity_factor) if annuity_factor else 200
            pension_amount = (
                float(balance) / factor
                if monthly_amount is None
                else float(monthly_amount)
            )

            pf = PensionFund(
                client_id=client_id,
                fund_name=asset_name,
                fund_type=fund_type,
                input_mode="manual",
                balance=float(balance),
                annuity_factor=factor,
                pension_amount=pension_amount,
                pension_start_date=start_date,
                indexation_method="none",
                tax_treatment=tax_treatment,
            )

            db.add(pf)
            db.commit()
            db.refresh(pf)

            response = {
                "success": True,
                "message": f"✅ נכס קצבה נוצר בהצלחה! שם: {asset_name}, יתרה: {float(balance):,.0f} ₪",
                "asset_id": pf.id,
                "asset_category": "pension",
                "asset_name": asset_name,
                "balance": float(balance),
                "pension_amount": pension_amount,
                "annuity_factor": factor,
            }

            logger.info(
                "✅ CREATE_INDIVIDUAL_ASSET (pension) completed: id=%d, balance=%s",
                pf.id,
                f"{float(balance):,.0f}",
            )

        elif asset_category == "capital":
            ca = CapitalAsset(
                client_id=client_id,
                asset_name=asset_name,
                asset_type=asset_type or "provident_fund",
                current_value=Decimal(str(balance)),
                monthly_income=Decimal(str(monthly_amount)) if monthly_amount else None,
                annual_return_rate=Decimal("0.03"),
                payment_frequency="monthly",
                start_date=start_date,
                indexation_method="none",
                tax_treatment=tax_treatment,
            )

            db.add(ca)
            db.commit()
            db.refresh(ca)

            response = {
                "success": True,
                "message": f"✅ נכס הון נוצר בהצלחה! שם: {asset_name}, ערך: {float(balance):,.0f} ₪",
                "asset_id": ca.id,
                "asset_category": "capital",
                "asset_name": asset_name,
                "current_value": float(balance),
                "monthly_income": float(monthly_amount) if monthly_amount else None,
            }

            logger.info(
                "✅ CREATE_INDIVIDUAL_ASSET (capital) completed: id=%d, value=%s",
                ca.id,
                f"{float(balance):,.0f}",
            )

        else:
            return f"Error: קטגוריית נכס לא תקינה: {asset_category}. ערכים אפשריים: pension, capital"

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("CREATE_INDIVIDUAL_ASSET failed: %s", e, exc_info=True)
        return f"Error: שגיאה ביצירת נכס: {str(e)}"
