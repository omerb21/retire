import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome

logger = logging.getLogger("app.llm_chat.tools")


def handle_create_additional_income(*, args: dict, client_id: int, db: Session) -> str:
    logger.info("💰 CREATE_ADDITIONAL_INCOME called - Creating additional income")

    try:
        source_type = args.get("source_type")
        amount = args.get("amount")
        frequency = args.get("frequency")
        start_date_str = args.get("start_date")
        end_date_str = args.get("end_date")
        tax_treatment = args.get("tax_treatment", "taxable")
        tax_rate = args.get("tax_rate")
        description = args.get("description")

        if not source_type:
            return "Error: חסר סוג מקור הכנסה (source_type)"
        if not amount:
            return "Error: חסר סכום (amount)"
        if not frequency:
            return "Error: חסרה תדירות (frequency)"
        if not start_date_str:
            return "Error: חסר תאריך התחלה (start_date)"

        from decimal import Decimal

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = (
            datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
        )

        income = AdditionalIncome(
            client_id=client_id,
            source_type=source_type,
            amount=Decimal(str(amount)),
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            tax_treatment=tax_treatment,
            tax_rate=Decimal(str(tax_rate)) if tax_rate else None,
            description=description,
            indexation_method="none",
        )

        db.add(income)
        db.commit()
        db.refresh(income)

        source_type_names = {
            "rental": "שכירות",
            "dividends": "דיבידנדים",
            "interest": "ריבית",
            "foreign_pension": 'פנסיה מחו"ל',
            "social_security": "ביטוח לאומי",
            "other": "אחר",
        }

        response = {
            "success": True,
            "message": f"✅ הכנסה נוספת נוצרה בהצלחה! סוג: {source_type_names.get(source_type, source_type)}, סכום: {float(amount):,.0f} ₪",
            "income_id": income.id,
            "source_type": source_type,
            "amount": float(amount),
            "frequency": frequency,
            "start_date": str(start_date),
            "end_date": str(end_date) if end_date else None,
            "tax_treatment": tax_treatment,
        }

        logger.info(
            "✅ CREATE_ADDITIONAL_INCOME completed: income_id=%d, type=%s, amount=%s",
            income.id,
            source_type,
            f"{float(amount):,.0f}",
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("CREATE_ADDITIONAL_INCOME failed: %s", e, exc_info=True)
        return f"Error: שגיאה ביצירת הכנסה נוספת: {str(e)}"
