"""Tests for Additional Income Service."""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome, IncomeSourceType, PaymentFrequency, IndexationMethod, TaxTreatment
from app.models.client import Client
from app.services.additional_income_service import AdditionalIncomeService
from app.providers.tax_params import InMemoryTaxParamsProvider


def test_calculate_monthly_amount(db_session: Session):
    """Test monthly amount calculation for different frequencies."""
    service = AdditionalIncomeService()
    
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Test monthly frequency
    monthly_income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    monthly_amount = service.calculate_monthly_amount(monthly_income)
    assert monthly_amount == Decimal('5000')
    
    # Test quarterly frequency
    quarterly_income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.DIVIDENDS,
        amount=Decimal('15000'),
        frequency=PaymentFrequency.QUARTERLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    monthly_amount = service.calculate_monthly_amount(quarterly_income)
    assert monthly_amount == Decimal('5000')  # 15000 / 3
    
    # Test annual frequency
    annual_income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.BUSINESS,
        amount=Decimal('60000'),
        frequency=PaymentFrequency.ANNUALLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    monthly_amount = service.calculate_monthly_amount(annual_income)
    assert monthly_amount == Decimal('5000')  # 60000 / 12


def test_apply_indexation_none(db_session: Session):
    """Test no indexation."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    base_amount = Decimal('5000')
    indexed_amount = service.apply_indexation(
        base_amount, income, date(2025, 1, 1)
    )
    
    assert indexed_amount == base_amount


def test_apply_indexation_fixed(db_session: Session):
    """Test fixed indexation."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.FIXED,
        fixed_rate=Decimal('0.03'),  # 3% annual
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    base_amount = Decimal('5000')
    # After 1 year with 3% indexation
    indexed_amount = service.apply_indexation(
        base_amount, income, date(2025, 1, 1)
    )
    
    expected = base_amount * Decimal('1.03')
    assert abs(indexed_amount - expected) < Decimal('0.01')


def test_calculate_tax_exempt(db_session: Session):
    """Test tax calculation for exempt income."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.EXEMPT
    )
    
    tax_amount = service.calculate_tax(Decimal('5000'), income)
    assert tax_amount == Decimal('0')


def test_calculate_tax_fixed_rate(db_session: Session):
    """Test tax calculation for fixed rate."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.25')  # 25%
    )
    
    tax_amount = service.calculate_tax(Decimal('5000'), income)
    assert tax_amount == Decimal('1250')  # 5000 * 0.25


def test_project_cashflow(db_session: Session):
    """Test cashflow projection."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('5000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.25')
    )
    
    cashflow = service.project_cashflow(
        income, 
        date(2024, 1, 1), 
        date(2024, 3, 31)
    )
    
    # Should have 3 months of cashflow
    assert len(cashflow) == 3
    
    # Check first item
    first_item = cashflow[0]
    assert first_item.date == date(2024, 1, 1)
    assert first_item.gross_amount == Decimal('5000')
    assert first_item.tax_amount == Decimal('1250')
    assert first_item.net_amount == Decimal('3750')
    assert first_item.source_type == IncomeSourceType.RENTAL


def test_generate_combined_cashflow(db_session: Session):
    """Test combined cashflow generation for multiple incomes."""
    service = AdditionalIncomeService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Create two income sources
    income1 = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('3000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.EXEMPT
    )
    
    income2 = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.DIVIDENDS,
        amount=Decimal('2000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.20')
    )
    
    db_session.add_all([income1, income2])
    db_session.commit()
    
    combined_cashflow = service.generate_combined_cashflow(
        db_session, 
        client.id, 
        date(2024, 1, 1), 
        date(2024, 2, 29)
    )
    
    # Should have 2 months of combined cashflow
    assert len(combined_cashflow) == 2
    
    # Check first month totals
    first_month = combined_cashflow[0]
    assert first_month['date'] == date(2024, 1, 1)
    assert first_month['gross_amount'] == Decimal('5000')  # 3000 + 2000
    assert first_month['tax_amount'] == Decimal('400')     # 0 + 400
    assert first_month['net_amount'] == Decimal('4600')    # 3000 + 1600
