import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.client import Client
from app.services.pension_fund_service import (
    calculate_pension_amount,
    compute_and_apply_indexation,
    compute_and_persist,
    compute_all_pension_funds,
    _compute_indexation_factor
)
from app.calculation.pensions import (
    calc_monthly_pension_from_capital,
    calc_pension_from_fund,
    apply_indexation,
    project_pension_cashflow
)
from app.calculation.pension_integration import (
    calculate_total_monthly_pension,
    generate_combined_pension_cashflow,
    integrate_pension_funds_with_scenario
)
from app.schemas.tax import TaxParameters
from app.providers.tax_params import TaxParamsProvider


@pytest.fixture
def sample_pension_fund():
    """Create a sample pension fund for testing"""
    return PensionFund(
        client_id=1,
        fund_name="Test Pension Fund",
        fund_type="Pension",
        input_mode="calculated",
        balance=1000000.0,
        annuity_factor=200.0,
        pension_amount=None,
        pension_start_date=date.today() - timedelta(days=365),
        indexation_method="none",
        fixed_index_rate=None,
        remarks="Test fund"
    )


@pytest.fixture
def sample_manual_pension_fund():
    """Create a sample pension fund with manual input mode for testing"""
    return PensionFund(
        client_id=1,
        fund_name="Manual Pension Fund",
        fund_type="Pension",
        input_mode="manual",
        balance=None,
        annuity_factor=None,
        pension_amount=5000.0,
        pension_start_date=date.today() - timedelta(days=365),
        indexation_method="fixed",
        fixed_index_rate=0.02,
        remarks="Manual test fund"
    )


@pytest.fixture
def sample_tax_params():
    """Create sample tax parameters for testing"""
    cpi_series = {
        date(2023, 1, 1): 100.0,
        date(2023, 6, 1): 102.0,
        date(2024, 1, 1): 105.0,
        date(2024, 6, 1): 107.0,
        date(2025, 1, 1): 110.0,
        date(2025, 6, 1): 112.0,
    }
    
    return TaxParameters(
        annuity_factor=200.0,
        cpi_series=cpi_series,
        tax_brackets=[],
        tax_credit=0.0,
        max_exempt=0.0
    )


def test_calculate_pension_amount_calculated(sample_pension_fund):
    """Test calculating pension amount for calculated input mode"""
    # Expected: balance / annuity_factor = 1000000 / 200 = 5000
    result = calculate_pension_amount(sample_pension_fund)
    assert result == 5000.0


def test_calculate_pension_amount_manual(sample_manual_pension_fund):
    """Test calculating pension amount for manual input mode"""
    result = calculate_pension_amount(sample_manual_pension_fund)
    assert result == 5000.0


def test_compute_indexation_factor_none():
    """Test computing indexation factor for 'none' method"""
    start_date = date(2023, 1, 1)
    today = date(2025, 1, 1)
    
    factor = _compute_indexation_factor("none", start_date, None, today)
    assert factor == 1.0


def test_compute_indexation_factor_fixed():
    """Test computing indexation factor for 'fixed' method"""
    start_date = date(2023, 1, 1)
    today = date(2025, 1, 1)  # 2 years difference
    fixed_rate = 0.02  # 2% annual
    
    factor = _compute_indexation_factor("fixed", start_date, fixed_rate, today)
    # Expected: (1 + 0.02)^2 = 1.0404
    assert round(factor, 4) == 1.0404


def test_compute_and_apply_indexation_none(sample_pension_fund):
    """Test computing and applying no indexation"""
    base, indexed = compute_and_apply_indexation(sample_pension_fund)
    assert base == 5000.0
    assert indexed == 5000.0  # No indexation, so same as base


def test_compute_and_apply_indexation_fixed(sample_manual_pension_fund):
    """Test computing and applying fixed indexation"""
    # Set reference date to 1 year after start date
    reference_date = sample_manual_pension_fund.pension_start_date + timedelta(days=365)
    
    base, indexed = compute_and_apply_indexation(sample_manual_pension_fund, reference_date)
    # Expected: 5000 * (1 + 0.02)^1 = 5100
    assert base == 5000.0
    assert indexed == 5100.0


def test_calc_pension_from_fund(sample_pension_fund, sample_tax_params):
    """Test calculating pension from fund"""
    result = calc_pension_from_fund(sample_pension_fund, sample_tax_params)
    assert result == 5000.0


def test_apply_indexation_fixed():
    """Test applying fixed indexation"""
    amount = 5000.0
    start_date = date(2023, 1, 1)
    reference_date = date(2025, 1, 1)  # 2 years difference
    fixed_rate = 0.02  # 2% annual
    
    result = apply_indexation(amount, "fixed", start_date, reference_date, fixed_rate)
    # Expected: 5000 * (1 + 0.02)^2 = 5202
    assert result == 5202.0


def test_apply_indexation_cpi(sample_tax_params):
    """Test applying CPI indexation"""
    amount = 5000.0
    start_date = date(2023, 1, 1)
    reference_date = date(2025, 1, 1)
    
    result = apply_indexation(amount, "cpi", start_date, reference_date, None, sample_tax_params)
    # Expected: 5000 * (110 / 100) = 5500
    assert result == 5500.0


def test_project_pension_cashflow(sample_pension_fund, sample_tax_params):
    """Test projecting pension cashflow"""
    months = 3
    reference_date = date(2025, 1, 1)
    
    cashflow = project_pension_cashflow(sample_pension_fund, months, sample_tax_params, reference_date)
    
    assert len(cashflow) == 3
    assert cashflow[0]["date"] == reference_date
    assert cashflow[0]["amount"] == 5000.0
    assert cashflow[0]["fund_name"] == "Test Pension Fund"
    
    # Check dates increment correctly
    assert cashflow[1]["date"] == date(2025, 2, 1)
    assert cashflow[2]["date"] == date(2025, 3, 1)


def test_calculate_total_monthly_pension(sample_pension_fund, sample_manual_pension_fund, sample_tax_params):
    """Test calculating total monthly pension from multiple funds"""
    funds = [sample_pension_fund, sample_manual_pension_fund]
    
    total = calculate_total_monthly_pension(funds, sample_tax_params)
    # Expected: 5000 + 5000 = 10000
    assert total == 10000.0


def test_compute_and_persist(db_session, sample_pension_fund):
    """Test computing and persisting pension fund calculations"""
    # Add client and fund to database
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()  # Ensure client.id has a value before using it
    sample_pension_fund.client_id = client.id
    db_session.add(sample_pension_fund)
    db_session.commit()
    
    # Compute and persist
    updated_fund = compute_and_persist(db_session, sample_pension_fund)
    
    # Check values were updated
    assert updated_fund.pension_amount == 5000.0
    assert updated_fund.indexed_pension_amount == 5000.0  # No indexation


def test_integrate_pension_funds_with_scenario(db_session):
    """Test integrating pension funds with scenario cashflow"""
    # Add client and fund to database
    client = Client(first_name="Test", last_name="User", id_number="987654321")
    db_session.add(client)
    db_session.flush()  # Ensure client.id has a value before using it
    db_session.commit()
    
    # Create a new pension fund with a different ID
    from app.models.pension_fund import PensionFund
    from datetime import date
    
    # Use the first day of the current month for consistent date matching
    today = date.today()
    first_day_of_month = date(today.year, today.month, 1)
    
    pension_fund = PensionFund(
        client_id=client.id,
        fund_name="Test Pension Fund 2",
        fund_type="Pension",
        input_mode="calculated",
        balance=1000000.0,
        annuity_factor=200.0,
        pension_start_date=first_day_of_month,
        indexation_method="none",
        remarks="Test fund"
    )
    db_session.add(pension_fund)
    db_session.commit()
    
    # Compute and persist pension amount
    from app.services.pension_fund_service import compute_and_persist
    updated_fund = compute_and_persist(db_session, pension_fund)
    print(f"Computed pension amount: {updated_fund.pension_amount}")

    # Create sample scenario cashflow using today's date and next month
    today = date.today()
    next_month = date(today.year, today.month + 1 if today.month < 12 else 1, 1)
    
    # Use the first day of the current month for scenario dates
    first_day_of_month = date(today.year, today.month, 1)
    first_day_of_next_month = date(today.year, today.month + 1 if today.month < 12 else 1, 1)

    scenario_cashflow = [
        {"date": first_day_of_month, "inflow": 10000.0, "outflow": 8000.0, "net": 2000.0},
        {"date": first_day_of_next_month, "inflow": 10000.0, "outflow": 8000.0, "net": 2000.0},
    ]

    # Explicitly pass the reference_date to ensure date alignment
    integrated = integrate_pension_funds_with_scenario(
        db_session, 
        client.id,
        scenario_cashflow,
        reference_date=first_day_of_month  # Use the same reference date as the pension start date
    )

    # Check integration
    assert len(integrated) == 2
    assert integrated[0]["pension_income"] == 5000.0
    assert integrated[0]["inflow"] == 15000.0  # 10000 + 5000
    assert integrated[0]["net"] == 7000.0  # 2000 + 5000
