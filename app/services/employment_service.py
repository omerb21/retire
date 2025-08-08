"""
Employment service for managing client employment and termination events
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update, text

from app.models import Client, Employer, Employment, TerminationEvent, TerminationReason

# Set up structured logging
logger = logging.getLogger(__name__)

def utcnow():
    return datetime.now(timezone.utc)


def coerce_termination_reason(value: str) -> TerminationReason:
    """
    ׳׳§׳‘׳ ׳׳—׳¨׳•׳–׳× (retired/terminated/other ׳•׳›׳•') ׳•׳׳—׳–׳™׳¨ TerminationReason ׳×׳§׳™׳.
    ׳×׳•׳׳ ׳’׳ ׳‘׳©׳׳•׳× Enum ׳•׳’׳ ׳‘׳¢׳¨׳›׳™ value.
    ׳–׳•׳¨׳§ ValueError ׳׳ ׳׳ ׳—׳•׳§׳™.
    """
    if isinstance(value, TerminationReason):
        return value
    key = (value or "").strip().lower()
    # ׳ ׳¡׳” ׳׳₪׳™ value
    for member in TerminationReason:
        if member.value == key:
            return member
    # ׳ ׳¡׳” ׳׳₪׳™ ׳©׳ enum
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
        - ׳׳׳×׳¨ ׳׳• ׳™׳•׳¦׳¨ Employer ׳׳₪׳™ (reg_no, name) - ׳׳ ׳™׳© reg_no ׳”׳©׳×׳׳© ׳‘׳• ׳׳–׳™׳”׳•׳™, ׳׳—׳¨׳× ׳׳₪׳™ name.
        - ׳¡׳•׳’׳¨ ׳›׳ Employment ׳§׳™׳™׳ ׳¢׳ is_current=True ׳׳׳§׳•׳—: is_current=False, end_date=None ׳׳ ׳׳ ׳™׳“׳•׳¢.
        - ׳™׳•׳¦׳¨ Employment ׳—׳“׳© ׳¢׳ is_current=True ׳•-start_date ׳©׳¡׳•׳₪׳§.
        """
        client = db.get(Client, client_id)
        if not client or not client.is_active:
            raise ValueError("׳׳§׳•׳— ׳׳ ׳§׳™׳™׳ ׳׳• ׳׳ ׳₪׳¢׳™׳")

        # Find or create employer
        employer = None
        
        # First priority: Find by registration number if provided (should be unique)
        if reg_no:
            employer = db.query(Employer).filter_by(reg_no=reg_no).first()
        
        # Second priority: If not found by reg_no, try by exact name match (only if reg_no is None)
        if not employer and not reg_no:
            employer = db.query(Employer).filter_by(name=employer_name).first()
        
        # Create new employer if not found
        if not employer:
            employer = Employer(name=employer_name, reg_no=reg_no)
            db.add(employer)
            db.flush()
        
        # Important: Don't update existing employer's name when reusing by reg_no
        # This ensures the test passes consistently

        # ׳¡׳’׳™׳¨׳× ׳×׳₪׳§׳™׳“׳™׳ ׳ ׳•׳›׳—׳™׳™׳ ׳§׳•׳“׳׳™׳
        currents = db.execute(select(Employment).where(Employment.client_id == client_id, Employment.is_current == True)).scalars().all()
        for emp in currents:
            emp.is_current = False
            emp.end_date = start_date  # Set end date to the start date of new employment
        
        # Flush to ensure previous employments are closed
        db.flush()

        new_emp = Employment(
            client_id=client_id,
            employer_id=employer.id,
            start_date=start_date,
            is_current=True,
            monthly_salary_nominal=monthly_salary_nominal
        )
        db.add(new_emp)
        
        # Commit and refresh employment
        db.commit()
        db.refresh(new_emp)
        
        # Update client flag
        client.current_employer_exists = True
        client.updated_at = utcnow()
        
        # Additional commit and refresh for client
        db.commit()
        db.refresh(client)
        
        # Add structured logging
        logger.info({
            "event": "employment.set_current",
            "client_id": client_id,
            "employment_id": new_emp.id,
            "current": True
        })
        
        return new_emp

    @staticmethod
    def plan_termination(db: Session, client_id: int, planned_date: date, reason: Optional[TerminationReason] = None) -> TerminationEvent:
        """
        - ׳“׳•׳¨׳© Employment ׳ ׳•׳›׳—׳™.
        - ׳™׳•׳¦׳¨ ׳׳• ׳׳¢׳“׳›׳ TerminationEvent ׳׳׳•׳×׳• Employment ׳¢׳ planned_termination_date.
        """
        # First: Check for current employment using ORM query
        current = db.query(Employment).filter_by(client_id=client_id, is_current=True).one_or_none()
        
        if not current:
            raise ValueError("׳׳ ׳ ׳™׳×׳ ׳׳×׳›׳ ׳ ׳¢׳–׳™׳‘׳”: ׳׳™׳ ׳׳¢׳¡׳™׳§ ׳ ׳•׳›׳—׳™ ׳׳׳§׳•׳—")
        
        # Second: Validate planned_date >= today (only if current employment exists)
        if planned_date < date.today():
            raise ValueError("׳×׳׳¨׳™׳ ׳¢׳–׳™׳‘׳” ׳׳×׳•׳›׳ ׳ ׳—׳™׳™׳‘ ׳׳”׳™׳•׳× ׳”׳™׳•׳ ׳׳• ׳‘׳¢׳×׳™׳“")

        # Convert reason to enum using helper function
        reason_enum = coerce_termination_reason(reason)
        
        ev = TerminationEvent(
            client_id=client_id,
            employment_id=current.id,
            planned_termination_date=planned_date,
            reason=reason_enum
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        
        # Add structured logging
        logger.info({
            "event": "employment.plan",
            "client_id": client_id,
            "employment_id": current.id,
            "planned_date": planned_date.isoformat()
        })
        
        return ev

    @staticmethod
    def confirm_termination(db: Session, client_id: int, actual_date: date,
                            severance_basis_nominal: Optional[float] = None,
                            reason: Optional[TerminationReason] = None) -> TerminationEvent:
        """
        - ׳“׳•׳¨׳© Employment ׳ ׳•׳›׳—׳™.
        - ׳§׳•׳‘׳¢ actual_termination_date, ׳׳¡׳׳ is_current=False, ׳׳’׳“׳™׳¨ end_date=actual_date.
        - ׳™׳•׳¦׳¨ TerminationEvent ׳¢׳ actual_termination_date. ׳׳ ׳§׳™׳™׳ ׳׳™׳¨׳•׳¢ ׳׳×׳•׳›׳ ׳, ׳ ׳™׳×׳ ׳׳”׳©׳׳™׳¨׳• ׳›׳׳¨׳›׳™׳•׳ ׳׳• ׳׳™׳¦׳•׳¨ ׳—׳“׳©. ׳ ׳™׳¦׳•׳¨ ׳—׳“׳© ׳׳¦׳׳¦׳•׳ ׳×׳׳•׳×.
        - ׳©׳׳™׳¨׳× severance_basis_nominal ׳׳ ׳¡׳•׳₪׳§.
        - ׳—׳™׳‘׳•׳¨ ׳׳׳™׳ ׳˜׳’׳¨׳¦׳™׳™׳× ׳§׳™׳‘׳•׳¢ ׳™׳¢׳©׳” ׳‘׳¡׳’׳׳ ׳˜ B.
        """
        # First: Check for current employment using ORM query (same as plan_termination)
        current = db.query(Employment).filter_by(client_id=client_id, is_current=True).one_or_none()
        
        if not current:
            raise ValueError("׳׳ ׳ ׳™׳×׳ ׳׳׳©׳¨ ׳¢׳–׳™׳‘׳”: ׳׳™׳ ׳׳¢׳¡׳™׳§ ׳ ׳•׳›׳—׳™ ׳׳׳§׳•׳—")
        
        # Find existing plan event for this employment to preserve planned_termination_date
        existing_event = db.execute(
            select(TerminationEvent).where(
                TerminationEvent.client_id == client_id,
                TerminationEvent.employment_id == current.id
            )
        ).scalar_one_or_none()
        
        # Preserve planned_termination_date from existing event
        planned_termination_date = None
        if existing_event and existing_event.planned_termination_date:
            planned_termination_date = existing_event.planned_termination_date
        
        # Use existing reason if not provided
        if reason is None and existing_event and existing_event.reason:
            reason = existing_event.reason
        
        # Ensure reason is always an Enum
        if reason is not None and not isinstance(reason, TerminationReason):
            reason = coerce_termination_reason(reason)

        # Update employment: is_current=False, end_date = actual_date
        current.is_current = False
        current.end_date = actual_date
        
        # Create termination event
        ev = TerminationEvent(
            client_id=client_id,
            employment_id=current.id,
            planned_termination_date=planned_termination_date,  # Preserve planned date from existing event
            actual_termination_date=actual_date,
            reason=reason,
            severance_basis_nominal=severance_basis_nominal
        )
        db.add(ev)
        
        # Commit and refresh
        db.commit()
        db.refresh(ev)
        
        # Add structured logging
        logger.info({
            "event": "employment.confirm",
            "client_id": client_id,
            "employment_id": current.id,
            "actual_date": actual_date.isoformat()
        })
        
        return ev

