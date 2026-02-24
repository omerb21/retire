import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CurrentEmployer
from app.services.current_employer import (
    EmploymentService as CurrentEmployerEmploymentService,
)

logger = logging.getLogger("app.llm_chat.tools")


def handle_set_current_employer_details(
    *, args: dict, client_id: int, db: Session
) -> str:
    logger.info("👔 SET_CURRENT_EMPLOYER_DETAILS called - Setting employer details")

    try:
        employer_name = args.get("employer_name")
        start_date_str = args.get("start_date")
        last_salary = args.get("last_salary")
        severance_accrued = args.get("severance_accrued")
        expected_retirement_date_str = args.get("expected_retirement_date")
        employer_id_number = args.get("employer_id_number")

        if not employer_name:
            return "Error: חסר שם מעסיק (employer_name)"
        if not start_date_str:
            return "Error: חסר תאריך תחילת עבודה (start_date)"
        if last_salary is None:
            return "Error: חסר שכר (last_salary)"

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        existing_employer = None
        try:
            existing_employer = CurrentEmployerEmploymentService(db).get_employer(
                client_id
            )
        except Exception:
            existing_employer = (
                db.query(CurrentEmployer)
                .filter(CurrentEmployer.client_id == client_id)
                .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
                .first()
            )

        if existing_employer:
            existing_employer.employer_name = employer_name
            existing_employer.start_date = start_date
            existing_employer.last_salary = float(last_salary)
            if severance_accrued is not None:
                existing_employer.severance_accrued = float(severance_accrued)
            if employer_id_number:
                existing_employer.employer_id_number = employer_id_number
            employer = existing_employer
            action = "עודכן"
        else:
            employer = CurrentEmployer(
                client_id=client_id,
                employer_name=employer_name,
                start_date=start_date,
                last_salary=float(last_salary),
                severance_accrued=(
                    float(severance_accrued) if severance_accrued else None
                ),
                employer_id_number=employer_id_number,
            )
            db.add(employer)
            action = "נוצר"

        db.commit()
        db.refresh(employer)

        response = {
            "success": True,
            "message": f"✅ מעסיק נוכחי {action} בהצלחה! שם: {employer_name}, שכר: {float(last_salary):,.0f} ₪",
            "employer_id": employer.id,
            "employer_name": employer_name,
            "start_date": str(start_date),
            "last_salary": float(last_salary),
            "severance_accrued": (
                float(severance_accrued) if severance_accrued else None
            ),
            "action": action,
        }

        logger.info(
            "✅ SET_CURRENT_EMPLOYER_DETAILS completed: employer_id=%d, action=%s",
            employer.id,
            action,
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("SET_CURRENT_EMPLOYER_DETAILS failed: %s", e, exc_info=True)
        return f"Error: שגיאה בעדכון פרטי מעסיק: {str(e)}"
