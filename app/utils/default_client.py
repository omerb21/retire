"""
Module for creating a default client in the system.
This client will be automatically loaded when the application starts.
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.models.current_employer import CurrentEmployer
from app.models.employer_grant import EmployerGrant

def create_default_client(db: Session):
    """Create a default client if it doesn't exist"""
    # Check if client already exists
    existing_client = db.query(Client).filter(Client.id_number == "123456789").first()
    if existing_client:
        print("Default client already exists")
        return existing_client
    
    # Create client
    client = Client(
        id_number="123456789",
        id_number_raw="123456789",
        full_name="ישראל ישראלי",
        first_name="ישראל",
        last_name="ישראלי",
        birth_date=date(1957, 1, 1),
        gender="זכר",  # זכר
        marital_status="נשוי",
        email="israel@gmail.com",
        phone="054-426144",
        pension_start_date=date(2024, 1, 1),  # 01/01/2024
        tax_credit_points=2.25  # 2.25 נקודות זיכוי
    )
    
    db.add(client)
    try:
        db.flush()  # Get the client ID without committing
        
        # Create pension funds
        pension_fund1 = PensionFund(
            client_id=client.id,
            fund_name="מקפת",
            pension_amount=5000,
            pension_start_date=date(2025, 1, 1),
            indexation_method="none",
            input_mode="manual"
        )
        
        pension_fund2 = PensionFund(
            client_id=client.id,
            fund_name="מנורה",
            pension_amount=6666,
            pension_start_date=date(2026, 1, 1),
            indexation_method="none",
            input_mode="manual"
        )
        
        db.add(pension_fund1)
        db.add(pension_fund2)
        
        # Create additional incomes
        income1 = AdditionalIncome(
            client_id=client.id,
            description="הכנסה עסקית",
            source_type="business",
            amount=25000,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            end_date=date(2030, 1, 1),
            indexation_method="none",
            tax_treatment="taxable"
        )
        
        income2 = AdditionalIncome(
            client_id=client.id,
            description="ביטוח לאומי",
            source_type="other",
            amount=2300,
            frequency="monthly",
            start_date=date(2024, 1, 1),
            end_date=date(2080, 1, 1),
            indexation_method="none",
            tax_treatment="exempt"
        )
        
        db.add(income1)
        db.add(income2)
        
        # Create capital asset
        asset = CapitalAsset(
            client_id=client.id,
            asset_name="דירה להשקעה",
            asset_type="rental_property",
            description="דירה להשכרה",
            current_value=3000000,
            monthly_income=8000,
            annual_return_rate=3,
            payment_frequency="monthly",
            start_date=date(2020, 1, 1),
            end_date=date(2080, 1, 1),
            indexation_method="none",
            tax_treatment="fixed_rate",
            tax_rate=0.1
        )
        
        db.add(asset)
        
        # Create current employer
        employer = CurrentEmployer(
            client_id=client.id,
            employer_name="מעסיק נוכחי",
            employer_id_number="123456789",
            start_date=date(2022, 1, 1),
            last_salary=20000,
            average_salary=20000,
            severance_accrued=10000,
            active_continuity="none",
            continuity_years=1.0
        )
        
        db.add(employer)
        db.flush()  # Get the employer ID
        
        # Create grants (previous employers)
        grant1 = EmployerGrant(
            employer_id=employer.id,
            grant_type="severance",
            grant_amount=100000,
            grant_date=date(1999, 12, 31)
            # מעסיק ראשון: 01/01/1985-31/12/1999
        )
        
        grant2 = EmployerGrant(
            employer_id=employer.id,
            grant_type="severance",
            grant_amount=90000,
            grant_date=date(2011, 12, 31)
            # מעסיק שני: 01/01/2000-31/12/2011
        )
        
        grant3 = EmployerGrant(
            employer_id=employer.id,
            grant_type="severance",
            grant_amount=80000,
            grant_date=date(2021, 12, 31)
            # מעסיק שלישי: 01/01/2012-31/12/2021
        )
        
        db.add(grant1)
        db.add(grant2)
        db.add(grant3)
        
        # Commit all changes
        db.commit()
        print("Default client created successfully")
        return client
        
    except IntegrityError as e:
        db.rollback()
        print(f"Error creating default client: {e}")
        return None

def ensure_default_client():
    """Ensure the default client exists in the database"""
    db = SessionLocal()
    try:
        create_default_client(db)
    finally:
        db.close()
