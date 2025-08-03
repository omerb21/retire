"""
Employment service for managing client employment and termination events
"""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.models import Client, Employer, Employment, TerminationEvent, TerminationReason


def coerce_termination_reason(value: str) -> TerminationReason:
    """
    מקבל מחרוזת (retired/terminated/other וכו') ומחזיר TerminationReason תקין.
    תומך גם בשמות Enum וגם בערכי value.
    זורק ValueError אם לא חוקי.
    """
    if isinstance(value, TerminationReason):
        return value
    key = (value or "").strip().lower()
    # נסה לפי value
    for member in TerminationReason:
        if member.value == key:
            return member
    # נסה לפי שם enum
    try:
        return TerminationReason[key]
    except Exception:
        raise ValueError(f"invalid_termination_reason: {value}")

class EmploymentService:
    @staticmethod
    def set_current_employer(db: Session, client_id: int,
                             employer_name: str,
                             reg_no: Optional[str],
                             start_date: date,
                             monthly_salary_nominal: Optional[float] = None) -> Employment:
        """
        - מאתר או יוצר Employer לפי (reg_no, name) - אם יש reg_no השתמש בו לזיהוי, אחרת לפי name.
        - סוגר כל Employment קיים עם is_current=True ללקוח: is_current=False, end_date=None אם לא ידוע.
        - יוצר Employment חדש עם is_current=True ו-start_date שסופק.
        """
        client = db.get(Client, client_id)
        if not client or not client.is_active:
            raise ValueError("לקוח לא קיים או לא פעיל")

        employer = None
        if reg_no:
            employer = db.execute(select(Employer).where(Employer.reg_no == reg_no)).scalar_one_or_none()
        if not employer:
            employer = db.execute(
                select(Employer).where(Employer.name == employer_name, Employer.reg_no.is_(None) if not reg_no else Employer.reg_no == reg_no)
            ).scalar_one_or_none()
        if not employer:
            employer = Employer(name=employer_name, reg_no=reg_no)
            db.add(employer)
            db.flush()

        # סגירת תפקידים נוכחיים קודמים
        currents = db.execute(select(Employment).where(Employment.client_id == client_id, Employment.is_current == True)).scalars().all()
        for emp in currents:
            emp.is_current = False
            # לא נכפה end_date כאן, יאושר בעת confirm_termination אם יש actual_date

        new_emp = Employment(
            client_id=client_id,
            employer_id=employer.id,
            start_date=start_date,
            is_current=True,
            monthly_salary_nominal=monthly_salary_nominal
        )
        db.add(new_emp)
        db.flush()
        return new_emp

    @staticmethod
    def plan_termination(db: Session, client_id: int, planned_date: date, reason: Optional[TerminationReason] = None) -> TerminationEvent:
        """
        - דורש Employment נוכחי.
        - יוצר או מעדכן TerminationEvent לאותו Employment עם planned_termination_date.
        """
        emp = db.execute(
            select(Employment).where(Employment.client_id == client_id, Employment.is_current == True)
        ).scalar_one_or_none()
        if not emp:
            raise ValueError("אין מעסיק נוכחי ללקוח")

        # Convert reason to enum using helper function
        reason_enum = coerce_termination_reason(reason)   # ← חשוב
        
        ev = TerminationEvent(
            client_id=client_id,
            employment_id=emp.id,
            planned_termination_date=planned_date,
            reason=reason_enum                  # ← לוודא שזה נשמר
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev

    @staticmethod
    def confirm_termination(db: Session, client_id: int, actual_date: date,
                            severance_basis_nominal: Optional[float] = None,
                            reason: Optional[TerminationReason] = None) -> TerminationEvent:
        """
        - דורש Employment נוכחי.
        - קובע actual_termination_date, מסמן is_current=False, מגדיר end_date=actual_date.
        - יוצר TerminationEvent עם actual_termination_date. אם קיים אירוע מתוכנן, ניתן להשאירו כארכיון או ליצור חדש. ניצור חדש לצמצום תלות.
        - שמירת severance_basis_nominal אם סופק.
        - חיבור לאינטגרציית קיבוע יעשה בסגמנט B.
        """
        emp = db.execute(
            select(Employment).where(Employment.client_id == client_id, Employment.is_current == True)
        ).scalar_one_or_none()
        if not emp:
            raise ValueError("אין מעסיק נוכחי ללקוח")

        emp.is_current = False
        emp.end_date = actual_date
        
        # Get existing termination event to preserve reason and planned_termination_date if not provided
        existing_event = db.execute(
            select(TerminationEvent).where(
                TerminationEvent.client_id == client_id,
                TerminationEvent.employment_id == emp.id
            )
        ).scalar_one_or_none()
        
        # Use existing reason if not provided
        if reason is None and existing_event and existing_event.reason:
            reason = existing_event.reason
            
        # Get planned_termination_date from existing event
        planned_termination_date = None
        if existing_event and existing_event.planned_termination_date:
            planned_termination_date = existing_event.planned_termination_date
        
        # Ensure reason is always an Enum
        if reason is not None and not isinstance(reason, TerminationReason):
            reason = coerce_termination_reason(reason)

        ev = TerminationEvent(
            client_id=client_id,
            employment_id=emp.id,
            planned_termination_date=planned_termination_date,  # Preserve planned date from existing event
            actual_termination_date=actual_date,
            reason=reason,  # Now guaranteed to be Enum or None
            severance_basis_nominal=severance_basis_nominal
        )
        db.add(ev)
        db.commit()  # Commit to ensure changes are persisted
        db.refresh(ev)  # Refresh to get latest data
        return ev
