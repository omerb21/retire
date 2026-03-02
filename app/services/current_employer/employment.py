"""
Employment Service Module
מודול שירותי העסקה
"""

import logging
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.schemas.current_employer import CurrentEmployerCreate, CurrentEmployerUpdate

logger = logging.getLogger("app.current_employer.employment")


class EmploymentService:
    """שירות ניהול העסקה"""

    def __init__(self, db: Session):
        """
        אתחול שירות העסקה

        Args:
            db: סשן מסד נתונים
        """
        self.db = db

    def _get_ordered_employer_candidates(self, client_id: int) -> list[CurrentEmployer]:
        return (
            self.db.execute(
                select(CurrentEmployer)
                .where(CurrentEmployer.client_id == client_id)
                .order_by(CurrentEmployer.updated_at.desc(), CurrentEmployer.id.desc())
            )
            .scalars()
            .all()
        )

    def _choose_current_employer(
        self, *, client_id: int, context_tag: str
    ) -> Optional[CurrentEmployer]:
        candidates = self._get_ordered_employer_candidates(client_id)
        candidate_ids = [
            int(getattr(c, "id", 0) or 0)
            for c in candidates
            if getattr(c, "id", None) is not None
        ]

        if len(candidates) > 1:
            logger.warning(
                "CURRENT_EMPLOYER_MULTIPLE_CANDIDATES client_id=%s context=%s count=%s candidate_ids=%s",
                client_id,
                context_tag,
                len(candidates),
                candidate_ids,
            )

        if not candidates:
            logger.info(
                "CURRENT_EMPLOYER_SELECTED client_id=%s context=%s selected_employer_id=%s reason=%s",
                client_id,
                context_tag,
                None,
                "none",
            )
            return None

        complete_candidates = [
            c
            for c in candidates
            if float(getattr(c, "severance_accrued", None) or 0.0) > 0.0
            and float(getattr(c, "last_salary", None) or 0.0) > 0.0
        ]
        complete_ids = [
            int(getattr(c, "id", 0) or 0)
            for c in complete_candidates
            if getattr(c, "id", None) is not None
        ]

        chosen = candidates[0]
        reason = "latest"

        if len(candidates) > 1 and complete_candidates:
            latest_severance = float(getattr(chosen, "severance_accrued", None) or 0.0)
            latest_salary = float(getattr(chosen, "last_salary", None) or 0.0)
            latest_missing_critical_fields = (
                latest_severance <= 0.0 or latest_salary <= 0.0
            )

            if latest_missing_critical_fields:
                chosen = complete_candidates[0]
                reason = "fallback_complete_due_to_missing_latest_fields"

        logger.info(
            "CURRENT_EMPLOYER_SELECTED client_id=%s context=%s selected_employer_id=%s start_date=%s end_date=%s last_salary=%s severance_accrued=%s candidate_count=%s candidate_ids=%s complete_candidate_ids=%s reason=%s",
            client_id,
            context_tag,
            getattr(chosen, "id", None),
            getattr(chosen, "start_date", None),
            getattr(chosen, "end_date", None),
            getattr(chosen, "last_salary", None),
            getattr(chosen, "severance_accrued", None),
            len(candidates),
            candidate_ids,
            complete_ids,
            reason,
        )

        return chosen

    def create_or_update_employer(
        self, client_id: int, employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        יצירה או עדכון מעסיק נוכחי

        Args:
            client_id: מזהה לקוח
            employer_data: נתוני מעסיק

        Returns:
            CurrentEmployer - מעסיק נוכחי

        Raises:
            ValueError: אם הלקוח לא נמצא
        """
        # בדיקת קיום לקוח
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if not client:
            raise ValueError("לקוח לא נמצא")

        ce = self._choose_current_employer(
            client_id=client_id,
            context_tag="EmploymentService.create_or_update_employer",
        )

        if ce:
            # עדכון מעסיק קיים
            return self._update_existing_employer(ce, employer_data)
        else:
            # יצירת מעסיק חדש
            return self._create_new_employer(client_id, employer_data)

    def _update_existing_employer(
        self, ce: CurrentEmployer, employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        עדכון מעסיק קיים

        Args:
            ce: מעסיק נוכחי קיים
            employer_data: נתונים חדשים

        Returns:
            CurrentEmployer מעודכן
        """
        severance_accrued_before = getattr(ce, "severance_accrued", None)
        payload_severance_accrued = getattr(employer_data, "severance_balance", None)
        if payload_severance_accrued is None:
            payload_severance_accrued = getattr(
                employer_data, "severance_accrued", None
            )

        # חשוב! לא לדרוס עם None
        data = employer_data.model_dump(exclude_none=True)

        # מיפוי שדות Frontend ל-DB
        if "monthly_salary" in data and data["monthly_salary"] is not None:
            data["last_salary"] = data["monthly_salary"]

        if "severance_balance" in data and data["severance_balance"] is not None:
            data["severance_accrued"] = data["severance_balance"]

        # הסרת שדות שלא קיימים בסכמת DB הנוכחית
        data.pop("monthly_salary", None)
        data.pop("severance_balance", None)

        # עדכון שדות
        for k, v in data.items():
            setattr(ce, k, v)
        ce.last_update = date.today()  # תמיד עדכון לפי שרת

        logger.info(
            "CURRENT_EMPLOYER_WRITE_PATH client_id=%s employer_id=%s source_tag=%s severance_accrued_before=%s severance_accrued_after=%s payload_severance_accrued=%s termination_date=%s",
            getattr(ce, "client_id", None),
            getattr(ce, "id", None),
            "api_update:EmploymentService._update_existing_employer",
            severance_accrued_before,
            getattr(ce, "severance_accrued", None),
            payload_severance_accrued,
            None,
        )

        self.db.add(ce)
        self.db.commit()
        self.db.refresh(ce)
        return ce

    def _create_new_employer(
        self, client_id: int, employer_data: CurrentEmployerCreate
    ) -> CurrentEmployer:
        """
        יצירת מעסיק חדש

        Args:
            client_id: מזהה לקוח
            employer_data: נתוני מעסיק

        Returns:
            CurrentEmployer חדש
        """
        # יצירה חדשה מהנתונים - מיפוי שדות Frontend ל-DB
        data = employer_data.model_dump(exclude_none=True)

        # מיפוי שדות
        if "monthly_salary" in data and data["monthly_salary"] is not None:
            data["last_salary"] = data["monthly_salary"]

        if "severance_balance" in data and data["severance_balance"] is not None:
            data["severance_accrued"] = data["severance_balance"]

        # הסרת שדות שלא קיימים בסכמת DB הנוכחית
        data.pop("monthly_salary", None)
        data.pop("severance_balance", None)

        ce = CurrentEmployer(client_id=client_id, **data)
        ce.last_update = date.today()

        self.db.add(ce)
        self.db.commit()
        self.db.refresh(ce)
        return ce

    def get_employer(self, client_id: int) -> Optional[CurrentEmployer]:
        """
        קבלת מעסיק נוכחי ללקוח

        Args:
            client_id: מזהה לקוח

        Returns:
            CurrentEmployer או None אם לא נמצא

        Raises:
            ValueError: אם הלקוח לא נמצא
        """
        # בדיקת קיום לקוח
        client = self.db.get(Client, client_id)
        if client is None:
            raise ValueError("לקוח לא נמצא")

        ce = self._choose_current_employer(
            client_id=client_id,
            context_tag="EmploymentService.get_employer",
        )

        if ce is None:
            raise ValueError("אין מעסיק נוכחי רשום ללקוח")

        return ce

    def update_employer_end_date(
        self, employer: CurrentEmployer, end_date: date
    ) -> CurrentEmployer:
        """
        עדכון תאריך סיום העסקה

        Args:
            employer: מעסיק נוכחי
            end_date: תאריך סיום

        Returns:
            CurrentEmployer מעודכן
        """
        employer.end_date = end_date
        self.db.add(employer)
        self.db.flush()
        return employer

    def clear_employer_end_date(self, employer: CurrentEmployer) -> CurrentEmployer:
        """
        ביטול תאריך סיום העסקה (ביטול עזיבה)

        Args:
            employer: מעסיק נוכחי

        Returns:
            CurrentEmployer מעודכן
        """
        employer.end_date = None
        self.db.add(employer)
        return employer
