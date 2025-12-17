import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger("app.llm_chat.tools")


def handle_create_tax_exempt_grant(*, args: dict, client_id: int, db: Session) -> str:
    logger.info("🎁 CREATE_TAX_EXEMPT_GRANT called - Creating tax exempt grant")

    try:
        employer_name = args.get("employer_name")
        grant_amount = args.get("grant_amount")
        work_start_date_str = args.get("work_start_date")
        work_end_date_str = args.get("work_end_date")
        grant_date_str = args.get("grant_date")

        if not employer_name:
            return "Error: חסר שם מעסיק (employer_name)"
        if not grant_amount:
            return "Error: חסר סכום מענק (grant_amount)"
        if not work_start_date_str:
            return "Error: חסר תאריך תחילת עבודה (work_start_date)"
        if not work_end_date_str:
            return "Error: חסר תאריך סיום עבודה (work_end_date)"

        from app.models.grant import Grant

        work_start_date = datetime.strptime(work_start_date_str, "%Y-%m-%d").date()
        work_end_date = datetime.strptime(work_end_date_str, "%Y-%m-%d").date()
        grant_date = (
            datetime.strptime(grant_date_str, "%Y-%m-%d").date()
            if grant_date_str
            else work_end_date
        )

        grant = Grant(
            client_id=client_id,
            employer_name=employer_name,
            work_start_date=work_start_date,
            work_end_date=work_end_date,
            grant_amount=float(grant_amount),
            grant_date=grant_date,
        )

        db.add(grant)
        db.commit()
        db.refresh(grant)

        response = {
            "success": True,
            "message": f"✅ מענק פטור נוצר בהצלחה! סכום: {float(grant_amount):,.0f} ₪ ממעסיק: {employer_name}",
            "grant_id": grant.id,
            "employer_name": employer_name,
            "grant_amount": float(grant_amount),
            "work_start_date": str(work_start_date),
            "work_end_date": str(work_end_date),
            "grant_date": str(grant_date),
        }

        logger.info(
            "✅ CREATE_TAX_EXEMPT_GRANT completed: grant_id=%d, amount=%s",
            grant.id,
            f"{float(grant_amount):,.0f}",
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("CREATE_TAX_EXEMPT_GRANT failed: %s", e, exc_info=True)
        return f"Error: שגיאה ביצירת מענק פטור: {str(e)}"
