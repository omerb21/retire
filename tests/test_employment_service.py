"""
Tests for employment service functionality
"""
import pytest
from datetime import date, datetime, timezone
from app.services.employment_service import EmploymentService
from app.models.client import Client
from app.models.employer import Employer
from app.models.employment import Employment
from app.models.termination_event import TerminationEvent, TerminationReason
from tests.utils import gen_reg_no, gen_valid_id

def utcnow():
    return datetime.now(timezone.utc)

def make_client(id_number_raw=None, full_name="׳™׳©׳¨׳׳ ׳™׳©׳¨׳׳׳™", is_active=True):
    """Factory function to create a test client with all required fields"""
    if id_number_raw is None:
        # Generate unique valid Israeli ID for each test
        id_number_raw = gen_valid_id()
    
    # Extract normalized id_number from raw (remove spaces, dashes)
    id_number = ''.join(filter(str.isdigit, id_number_raw))
    
    return Client(
        id_number_raw=id_number_raw,
        id_number=id_number,
        full_name=full_name,
        is_active=is_active,
        address_city="׳×׳ ׳׳‘׳™׳‘",
        address_street="׳¨׳—׳•׳‘ ׳”׳‘׳“׳™׳§׳” 1",
        address_postal_code="12345",
        birth_date=date(1980, 1, 1),
        email=f"test{id_number_raw[-4:]}@example.com",
        phone="050-1234567",
        created_at=utcnow(),
        updated_at=utcnow()
    )

def test_set_current_employer_creates_employment_and_employer(db_session):
    """Test creating employment with new employer"""
    # Arrange
    client = make_client()
    db_session.add(client)
    db_session.commit()
    
    # Act
    employment = EmploymentService.set_current_employer(
        db=db_session,
        client_id=client.id,
        employer_name="׳—׳‘׳¨׳× ׳˜׳¡׳˜ ׳‘׳¢\"׳",
        reg_no=gen_reg_no(),
        start_date=date(2023, 1, 1),
        monthly_salary_nominal=10000.0
    )
    
    # Assert
    assert employment is not None
    assert employment.client_id == client.id
    assert employment.is_current == True
    assert employment.start_date == date(2023, 1, 1)
    assert employment.monthly_salary_nominal == 10000.0
    
    # Check employer was created
    employer = db_session.get(Employer, employment.employer_id)
    assert employer.name == "׳—׳‘׳¨׳× ׳˜׳¡׳˜ ׳‘׳¢\"׳"
    # reg_no is generated dynamically, just check it exists
    assert employer.reg_no is not None

def test_set_current_employer_reuses_existing_employer_by_reg_no(db_session):
    """Test reusing existing employer when reg_no matches"""
    # Arrange - create existing employer
    test_reg_no = gen_reg_no()
    existing_employer = Employer(name="׳—׳‘׳¨׳” ׳™׳©׳ ׳”", reg_no=test_reg_no)
    db_session.add(existing_employer)
    db_session.commit()
    
    client = make_client()
    db_session.add(client)
    db_session.commit()
    
    # Act
    employment = EmploymentService.set_current_employer(
        db=db_session,
        client_id=client.id,
        employer_name="׳—׳‘׳¨׳× ׳˜׳¡׳˜ ׳‘׳¢\"׳",  # Different name
        reg_no=test_reg_no,  # Same reg_no
        start_date=date(2023, 1, 1),
        monthly_salary_nominal=10000.0
    )
    
    # Assert - should reuse existing employer
    assert employment.employer_id == existing_employer.id
    
    # Check that employer name wasn't changed
    employer = db_session.get(Employer, employment.employer_id)
    assert employer.name == "׳—׳‘׳¨׳” ׳™׳©׳ ׳”"

def test_plan_termination_creates_termination_event(db_session):
    """Test planning termination for client with current employment"""
    # Arrange - create current employment
    client = make_client()
    db_session.add(client)
    db_session.commit()
    
    employment = EmploymentService.set_current_employer(
        db=db_session,
        client_id=client.id,
        employer_name="׳—׳‘׳¨׳× ׳˜׳¡׳˜",
        reg_no=None,
        start_date=date(2023, 1, 1),
        monthly_salary_nominal=10000.0
    )
    db_session.commit()
    
    # Act
    from datetime import date as _date
    future_date = _date.today().replace(year=_date.today().year + 1)
    termination_event = EmploymentService.plan_termination(
        db=db_session,
        client_id=client.id,
        planned_date=future_date,
        reason=TerminationReason.retired
    )
    
    # Assert
    assert termination_event is not None
    assert termination_event.client_id == client.id
    assert termination_event.employment_id == employment.id
    assert termination_event.planned_termination_date == future_date
    assert termination_event.reason == TerminationReason.retired
    assert termination_event.actual_termination_date is None

def test_plan_termination_fails_without_current_employment(db_session):
    """Test that planning termination fails when no current employment exists"""
    # Arrange
    client = make_client()
    db_session.add(client)
    db_session.commit()
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        EmploymentService.plan_termination(
            db=db_session,
            client_id=client.id,
            planned_date=date(2023, 12, 31)
        )
    msg = str(exc_info.value); assert isinstance(msg, str) and len(msg) > 0
def test_confirm_termination_updates_employment_and_creates_event(db_session):
    """Test confirming termination updates employment and creates termination event"""
    # Arrange - create current employment
    client = make_client()
    db_session.add(client)
    db_session.commit()
    
    employment = EmploymentService.set_current_employer(
        db=db_session,
        client_id=client.id,
        employer_name="׳—׳‘׳¨׳× ׳˜׳¡׳˜",
        reg_no=None,
        start_date=date(2023, 1, 1),
        monthly_salary_nominal=10000.0
    )
    db_session.commit()
    
    # Act
    termination_event = EmploymentService.confirm_termination(
        db=db_session,
        client_id=client.id,
        actual_date=date(2023, 6, 30)
    )
    
    # Assert
    assert termination_event is not None
    assert termination_event.client_id == client.id
    assert termination_event.employment_id == employment.id
    assert termination_event.actual_termination_date == date(2023, 6, 30)
    
    # Check employment was updated
    db_session.refresh(employment)
    assert employment.is_current == False
    assert employment.end_date == date(2023, 6, 30)

