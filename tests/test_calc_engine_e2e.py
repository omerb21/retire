from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Client, Employment, Employer
from app.providers.tax_params import InMemoryTaxParamsProvider
from app.calculation.engine import CalculationEngine
from app.schemas.scenario import ScenarioIn

def make_db():
    engine = create_engine("sqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def test_engine_e2e_minimal():
    db = make_db()
    # Arrange: client + employer + employment
    c = Client(
        id_number_raw="111111118",
        id_number="111111118",
        full_name="ישראלי בדיקה",
        birth_date=date(1980,1,1),
        email="t@t.com", phone="0500000000",
        is_active=True
    )
    db.add(c); db.commit(); db.refresh(c)
    
    employer = Employer(
        name="מעסיק בדיקה",
        reg_no="123456789"
    )
    db.add(employer); db.commit(); db.refresh(employer)
    
    emp = Employment(client_id=c.id, employer_id=employer.id, start_date=date(2023,1,1), is_current=True)
    db.add(emp); db.commit()

    engine = CalculationEngine(db, InMemoryTaxParamsProvider())
    scenario = ScenarioIn(
        planned_termination_date=date.today() + timedelta(days=30),
        monthly_expenses=5000.0,
        other_incomes_monthly=None
    )
    out = engine.run(c.id, scenario)

    assert out.seniority_years > 1.0
    assert out.grant_gross > 100000.0  # אחרי הצמדה
    assert out.grant_tax >= 0.0
    assert out.pension_monthly > 0.0
    assert len(out.cashflow) == 12
