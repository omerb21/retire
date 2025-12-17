import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CurrentEmployer

logger = logging.getLogger("app.llm_chat.tools")


def handle_execute_work_termination(*, args: dict, client_id: int, db: Session) -> str:
    logger.info("🚪 EXECUTE_WORK_TERMINATION called - Executing work termination")

    try:
        termination_date_str = args.get("termination_date")
        termination_reason = args.get("termination_reason")
        final_salary = args.get("final_salary")
        calculate_severance = args.get("calculate_severance", True)

        if not termination_date_str:
            return "Error: חסר תאריך סיום עבודה (termination_date)"
        if not termination_reason:
            return "Error: חסרה סיבת סיום (termination_reason)"

        termination_date = datetime.strptime(termination_date_str, "%Y-%m-%d").date()

        employer = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).first()

        if not employer:
            return "Error: לא נמצא מעסיק נוכחי. יש להגדיר מעסיק תחילה באמצעות SET_CURRENT_EMPLOYER_DETAILS."

        employer.end_date = termination_date
        if final_salary is not None:
            employer.last_salary = float(final_salary)

        severance_info = None
        if calculate_severance and employer.last_salary and employer.start_date:
            years_of_service = (termination_date - employer.start_date).days / 365.25
            salary = float(final_salary) if final_salary else float(employer.last_salary)
            severance_amount = salary * years_of_service

            annual_cap = 13310  # 2024 ceiling
            exempt_amount = min(severance_amount, annual_cap * years_of_service)
            taxable_amount = max(0, severance_amount - exempt_amount)

            severance_info = {
                "years_of_service": round(years_of_service, 2),
                "last_salary": salary,
                "severance_amount": round(severance_amount, 2),
                "exempt_amount": round(exempt_amount, 2),
                "taxable_amount": round(taxable_amount, 2),
            }

        db.commit()

        reason_names = {
            "resignation": "התפטרות",
            "layoff": "פיטורים",
            "retirement": "פרישה",
            "other": "אחר",
        }

        response = {
            "success": True,
            "message": f"✅ עזיבת עבודה נרשמה בהצלחה! סיבה: {reason_names.get(termination_reason, termination_reason)}",
            "employer_name": employer.employer_name,
            "termination_date": str(termination_date),
            "termination_reason": termination_reason,
            "severance_calculated": severance_info,
            "next_steps": [
                "יש להחליט על אופן הטיפול בפיצויים (משיכה/רצף קצבה)",
                "ניתן להשתמש בכלי PROCESS_TERMINATION לביצוע ההחלטה",
            ],
        }

        logger.info(
            "✅ EXECUTE_WORK_TERMINATION completed: employer=%s, date=%s",
            employer.employer_name,
            termination_date,
        )

        return json.dumps(response, ensure_ascii=False)

    except Exception as e:
        logger.error("EXECUTE_WORK_TERMINATION failed: %s", e, exc_info=True)
        return f"Error: שגיאה בביצוע עזיבת עבודה: {str(e)}"
