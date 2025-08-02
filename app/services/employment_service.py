"""
Employment service for managing client employment and termination events
"""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.models import Client, Employer, Employment, TerminationEvent, TerminationReason

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

        ev = TerminationEvent(
            client_id=client_id,
            employment_id=emp.id,
            planned_termination_date=planned_date,
            reason=reason
        )
        db.add(ev)
        db.flush()
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

        ev = TerminationEvent(
            client_id=client_id,
            employment_id=emp.id,
            actual_termination_date=actual_date,
            reason=reason,
            severance_basis_nominal=severance_basis_nominal
        )
        db.add(ev)
        db.flush()
        return ev
