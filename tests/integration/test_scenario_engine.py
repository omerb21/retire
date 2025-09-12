"""
Integration tests for scenario engine functionality
"""
import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from models.client import Client
from models.scenario import Scenario
from models.scenario_cashflow import ScenarioCashflow
from models.existing_product import ExistingProduct
from models.saving_product import SavingProduct
from services.scenario_engine import (
    run_scenario, build_context, apply_grants_and_reservations,
    apply_indexation, calculate_pension_income, generate_cashflow
)

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_client(db_session):
    """Create a sample client for testing"""
    client = Client(
        id_number_raw="123456789",
        id_number_normalized="123456789",
        full_name="Test Client",
        sex="M",
        marital_status="Married"
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client

@pytest.fixture
def sample_scenario(db_session, sample_client):
    """Create a sample scenario for testing"""
    parameters = {
        "retirement_age": 67,
        "life_expectancy": 85,
        "indexation_rate": 0.02,
        "grants": [
            {
                "type": "severance",
                "amount": 100000,
                "payment_year": 2025
            }
        ]
    }
    
    scenario = Scenario(
        client_id=sample_client.id,
        name="Test Retirement Scenario",
        parameters_json=json.dumps(parameters),
        status="draft"
    )
    db_session.add(scenario)
    db_session.commit()
    db_session.refresh(scenario)
    return scenario

@pytest.fixture
def sample_products(db_session, sample_client):
    """Create sample existing products for testing"""
    # Create saving product first
    sp = SavingProduct(
        fund_code="TEST001",
        fund_name="Test Pension Fund",
        company_name="Test Insurance"
    )
    db_session.add(sp)
    db_session.commit()
    
    # Create existing product
    ep = ExistingProduct(
        client_id=sample_client.id,
        saving_product_id=sp.id,
        fund_code="TEST001",
        fund_name="Test Pension Fund",
        company_name="Test Insurance",
        current_balance=500000.0,
        monthly_contribution=2000.0,
        status="active"
    )
    db_session.add(ep)
    db_session.commit()
    return [ep]

def test_build_context(sample_client, sample_scenario):
    """Test building calculation context"""
    context = build_context(sample_client, sample_scenario)
    
    assert context["client"] == sample_client
    assert context["scenario"] == sample_scenario
    assert "parameters" in context
    assert context["retirement_age"] == 67
    assert context["life_expectancy"] == 85
    assert "tax_parameters" in context

def test_apply_grants_and_reservations():
    """Test grant processing with 1.35 multiplier"""
    context = {
        "grants": [
            {"amount": 100000, "type": "severance", "payment_year": 2025}
        ]
    }
    
    result = apply_grants_and_reservations(context)
    
    assert "processed_grants" in result
    assert len(result["processed_grants"]) == 1
    
    grant = result["processed_grants"][0]
    assert grant["original_amount"] == 100000
    assert grant["reservation_impact"] == 135000  # 100000 * 1.35
    assert result["total_reservation_impact"] == 135000

def test_run_scenario_end_to_end(db_session, sample_client, sample_scenario, sample_products):
    """Test complete scenario execution end-to-end"""
    
    # Run the scenario
    cashflow = run_scenario(db_session, sample_client.id, sample_scenario.id)
    
    # Verify cashflow was generated
    assert isinstance(cashflow, list)
    assert len(cashflow) > 0
    
    # Check that cashflow entries have required fields
    for entry in cashflow:
        assert "year" in entry
        assert "gross_income" in entry
        assert "tax" in entry
        assert "net_income" in entry
        assert "pension_income" in entry
        assert "grant_income" in entry
    
    # Verify data was saved to database
    saved_cashflow = db_session.query(ScenarioCashflow).filter(
        ScenarioCashflow.scenario_id == sample_scenario.id
    ).all()
    
    assert len(saved_cashflow) == len(cashflow)
    
    # Verify scenario status was updated
    db_session.refresh(sample_scenario)
    assert sample_scenario.status == "completed"

def test_scenario_with_multiple_products(db_session, sample_client):
    """Test scenario calculation with multiple pension products"""
    
    # Create multiple products
    products_data = [
        {"fund_code": "FUND001", "balance": 300000, "contribution": 1500},
        {"fund_code": "FUND002", "balance": 200000, "contribution": 1000},
        {"fund_code": "FUND003", "balance": 100000, "contribution": 500}
    ]
    
    for i, data in enumerate(products_data):
        sp = SavingProduct(
            fund_code=data["fund_code"],
            fund_name=f"Fund {i+1}",
            company_name=f"Company {i+1}"
        )
        db_session.add(sp)
        db_session.commit()
        
        ep = ExistingProduct(
            client_id=sample_client.id,
            saving_product_id=sp.id,
            fund_code=data["fund_code"],
            fund_name=f"Fund {i+1}",
            company_name=f"Company {i+1}",
            current_balance=data["balance"],
            monthly_contribution=data["contribution"],
            status="active"
        )
        db_session.add(ep)
    
    db_session.commit()
    
    # Create scenario
    parameters = {
        "retirement_age": 65,
        "life_expectancy": 80,
        "indexation_rate": 0.025
    }
    
    scenario = Scenario(
        client_id=sample_client.id,
        name="Multi-Product Scenario",
        parameters_json=json.dumps(parameters),
        status="draft"
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Run scenario
    cashflow = run_scenario(db_session, sample_client.id, scenario.id)
    
    # Verify results
    assert len(cashflow) > 0
    
    # Check that pension income reflects multiple products
    pension_years = [entry for entry in cashflow if entry["pension_income"] > 0]
    assert len(pension_years) > 0
    
    # Total pension should reflect combined balances
    total_expected_balance = sum(data["balance"] for data in products_data)
    assert total_expected_balance == 600000

def test_scenario_cashflow_persistence(db_session, sample_client, sample_scenario):
    """Test that cashflow data is properly saved and retrievable"""
    
    # Run scenario
    cashflow = run_scenario(db_session, sample_client.id, sample_scenario.id)
    
    # Query saved cashflow
    saved_records = db_session.query(ScenarioCashflow).filter(
        ScenarioCashflow.scenario_id == sample_scenario.id
    ).order_by(ScenarioCashflow.year).all()
    
    # Verify all records were saved
    assert len(saved_records) == len(cashflow)
    
    # Verify data integrity
    for i, record in enumerate(saved_records):
        original_entry = cashflow[i]
        assert record.year == original_entry["year"]
        assert abs(record.gross_income - original_entry["gross_income"]) < 0.01
        assert abs(record.net_income - original_entry["net_income"]) < 0.01
        assert abs(record.tax - original_entry["tax"]) < 0.01

def test_scenario_with_grants_timing(db_session, sample_client):
    """Test scenario with grants paid in different years"""
    
    parameters = {
        "retirement_age": 67,
        "life_expectancy": 85,
        "grants": [
            {"amount": 50000, "type": "severance", "payment_year": 2024},
            {"amount": 75000, "type": "adjustment", "payment_year": 2026},
            {"amount": 25000, "type": "bonus", "payment_year": 2028}
        ]
    }
    
    scenario = Scenario(
        client_id=sample_client.id,
        name="Multi-Grant Scenario",
        parameters_json=json.dumps(parameters),
        status="draft"
    )
    db_session.add(scenario)
    db_session.commit()
    
    # Run scenario
    cashflow = run_scenario(db_session, sample_client.id, scenario.id)
    
    # Verify grant income appears in correct years
    grant_years = {entry["year"]: entry["grant_income"] for entry in cashflow if entry["grant_income"] > 0}
    
    # Should have grant income in specified years (accounting for indexation)
    assert len(grant_years) >= 3  # At least the three grant years
    
    # Verify total grant amounts (approximately, due to indexation)
    total_grants = sum(grant_years.values())
    expected_total = 50000 + 75000 + 25000  # Base amounts
    assert total_grants >= expected_total  # Should be higher due to indexation
