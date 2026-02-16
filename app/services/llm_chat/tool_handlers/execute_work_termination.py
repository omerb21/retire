import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import CurrentEmployer
from app.services.current_employer import TerminationService
from app.services.current_employer.termination_parts.termination_amounts_ssot import (
    compute_termination_amounts_ssot,
)

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
            termination_service = TerminationService(db)
            salary = float(final_salary) if final_salary else float(employer.last_salary)
            calc = termination_service.calculate_severance(
                start_date=employer.start_date,
                end_date=termination_date,
                last_salary=salary,
                continuity_years=float(getattr(employer, "continuity_years", 0.0) or 0.0),
            )

            try:
                years_of_service = float(calc.get("service_years") or 0)
            except Exception:
                years_of_service = 0.0

            try:
                formula_total = float(calc.get("severance_amount") or 0)
            except Exception:
                formula_total = 0.0

            try:
                exempt_amount = float(calc.get("exempt_amount") or 0)
            except Exception:
                exempt_amount = 0.0

            try:
                accrued_total = float(getattr(employer, "severance_accrued", 0) or 0)
            except Exception:
                accrued_total = 0.0

            ssot = compute_termination_amounts_ssot(
                formula_total=formula_total,
                accrued_total=accrued_total,
                exempt_amount=exempt_amount,
            )

            severance_total = float(ssot.get("severance_total") or 0)
            taxable_amount = float(ssot.get("taxable_amount") or 0)

            severance_info = {
                "years_of_service": round(years_of_service, 2),
                "last_salary": salary,
                "severance_amount": round(severance_total, 2),
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
