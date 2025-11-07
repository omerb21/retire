"""
Client case detection service for workflow determination
"""
from datetime import date
from sqlalchemy.orm import Session
from typing import List, Optional
from types import SimpleNamespace

from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.additional_income import AdditionalIncome
from app.schemas.case import ClientCase, CaseDetectionResult
from app.utils.calculation_log import log_calc

def detect_case(db: Session, client_id: int, *, retirement_age: int = 67) -> CaseDetectionResult:
    """
    Detect client case based on specified rules
    
    Rules:
    1. If client age >= retirement_age => Case 3 (PAST_RETIREMENT_AGE)
    2. If no current employer and has business income => Case 2 (SELF_EMPLOYED_ONLY)
    3. If no current employer and no business income => Case 1 (NO_CURRENT_EMPLOYER)
    4. If has current employer and no planned leave => Case 4 (ACTIVE_NO_LEAVE)
    5. If has current employer and planned leave => Case 5 (REGULAR_WITH_LEAVE)
    
    Args:
        db: Database session
        client_id: Client ID
        retirement_age: Retirement age threshold (default: 67)
        
    Returns:
        CaseDetectionResult with client_id, case_id, case_name, and reasons
    """
    # Get client data
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client with ID {client_id} not found")
    
    # Check if client's birth date is available
    if not client.birth_date:
        raise ValueError(f"Client {client_id} has no birth date - cannot determine age")
    
    # Calculate current age
    today = date.today()
    age = today.year - client.birth_date.year - ((today.month, today.day) < (client.birth_date.month, client.birth_date.day))
    
    reasons: List[str] = []
    
    # Check if client is past retirement age (Case 3)
    if age >= retirement_age:
        case_id = ClientCase.PAST_RETIREMENT_AGE
        case_name = ClientCase.PAST_RETIREMENT_AGE.value
        reasons.append(f"client_age_{age}_exceeds_retirement_age_{retirement_age}")
    else:
        # Check for current employer
        current_employer = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).first()
        
        if not current_employer:
            # No current employer - check for business income (Case 2 vs Case 1)
            business_income = db.query(AdditionalIncome).filter(
                AdditionalIncome.client_id == client_id,
                AdditionalIncome.source_type == "business"
            ).first()
            
            if business_income:
                case_id = ClientCase.SELF_EMPLOYED_ONLY
                case_name = ClientCase.SELF_EMPLOYED_ONLY.value
                reasons.append("no_current_employer")
                reasons.append("has_business_income")
            else:
                case_id = ClientCase.NO_CURRENT_EMPLOYER
                case_name = ClientCase.NO_CURRENT_EMPLOYER.value
                reasons.append("no_current_employer")
                reasons.append("no_business_income")
        else:
            # Has current employer - check for planned leave (Case 4 vs Case 5)
            has_planned_leave = bool(
                current_employer.end_date or 
                client.planned_termination_date
            )
            
            if not has_planned_leave:
                case_id = ClientCase.ACTIVE_NO_LEAVE
                case_name = ClientCase.ACTIVE_NO_LEAVE.value
                reasons.append("has_current_employer")
                reasons.append("no_planned_leave")
            else:
                case_id = ClientCase.REGULAR_WITH_LEAVE
                case_name = ClientCase.REGULAR_WITH_LEAVE.value
                reasons.append("has_current_employer")
                if current_employer.end_date:
                    reasons.append(f"employer_end_date_set_{current_employer.end_date}")
                elif client.planned_termination_date:
                    reasons.append(f"planned_termination_date_set_{client.planned_termination_date}")
                else:
                    reasons.append("planned_leave_detected_or_default")
    
    # Create result
    result = CaseDetectionResult(
        client_id=client_id,
        case_id=case_id,
        case_name=case_name,
        reasons=reasons
    )
    
    # Log the case detection
    log_calc(
        event="case_detected",
        payload={"client_id": client_id, "retirement_age": retirement_age},
        result=result.dict(),
        debug_info={
            "client_age": age,
            "birth_date": str(client.birth_date),
        }
    )
    
    return result

def detect_case_with_session(db_session, client_id):
    """
    Detect client case using provided db_session. Returns an object with attribute case_id
    where case_id is a ClientCase enum member.
    """
    # Try session.get (SQLAlchemy 1.4+), fallback to query
    client = None
    try:
        client = db_session.get(Client, client_id)
    except Exception:
        try:
            client = db_session.query(Client).filter_by(id=client_id).one_or_none()
        except Exception:
            client = None

    if client is None:
        raise ValueError(f"Client with ID {client_id} not found")

    # Calculate age for retirement check
    from datetime import date
    retirement_age = 67  # placeholder - replace with real domain rule
    age = calculate_age(client.birth_date) if getattr(client, "birth_date", None) else 0

    if age >= retirement_age:
        detected = ClientCase.PAST_RETIREMENT_AGE
    else:
        # Check for current employer
        current_employer = db_session.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).first()
        
        if not current_employer:
            # No current employer - check for business income
            business_income = db_session.query(AdditionalIncome).filter(
                AdditionalIncome.client_id == client_id,
                AdditionalIncome.source_type == "business"
            ).first()
            
            if business_income:
                detected = ClientCase.SELF_EMPLOYED_ONLY
            else:
                detected = ClientCase.NO_CURRENT_EMPLOYER
        else:
            # Has current employer - check for planned leave
            has_planned_leave = bool(
                current_employer.end_date or 
                getattr(client, 'planned_termination_date', None)
            )
            
            if not has_planned_leave:
                detected = ClientCase.ACTIVE_NO_LEAVE
            else:
                detected = ClientCase.REGULAR_WITH_LEAVE

    # Ensure returned object has attribute case_id of type ClientCase
    result = SimpleNamespace(case_id=detected)
    return result
def calculate_age(birth_date, as_of_date=None):
    """
    Temporary calculate_age stub.
    Accepts date/datetime or ISO date string and returns integer years.
    Replace with domain-accurate implementation later.
    """
    from datetime import datetime, date
    # parse string input
    if isinstance(birth_date, str):
        try:
            birth_date = datetime.fromisoformat(birth_date).date()
        except Exception:
            # try common formats dd/mm/yyyy
            parts = birth_date.replace("-", "/").split("/")
            if len(parts) == 3:
                day, month, year = parts
                birth_date = date(int(year), int(month), int(day))
            else:
                raise
    if as_of_date is None:
        as_of_date = date.today()
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()
    years = as_of_date.year - birth_date.year - ((as_of_date.month, as_of_date.day) < (birth_date.month, birth_date.day))
    return years
