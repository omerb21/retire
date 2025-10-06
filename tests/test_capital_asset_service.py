"""Tests for Capital Asset Service."""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset, AssetType, PaymentFrequency, IndexationMethod, TaxTreatment
from app.models.client import Client
from app.services.capital_asset_service import CapitalAssetService
from app.providers.tax_params import InMemoryTaxParamsProvider


def test_calculate_monthly_return(db_session: Session):
    """Test monthly return calculation for different frequencies."""
    service = CapitalAssetService()
    
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Test monthly frequency
    monthly_asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.06'),  # 6% annual
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    monthly_return = service.calculate_monthly_return(monthly_asset)
    expected = Decimal('100000') * Decimal('0.06') / Decimal('12')  # 500
    assert abs(monthly_return - expected) < Decimal('0.01')
    
    # Test quarterly frequency
    quarterly_asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.BONDS,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.04'),  # 4% annual
        payment_frequency=PaymentFrequency.QUARTERLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    quarterly_return = service.calculate_monthly_return(quarterly_asset)
    expected = Decimal('100000') * Decimal('0.04') / Decimal('4')  # 1000
    assert abs(quarterly_return - expected) < Decimal('0.01')


def test_apply_indexation_none(db_session: Session):
    """Test no indexation."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.06'),
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    base_return = Decimal('500')
    indexed_return = service.apply_indexation(
        base_return, asset, date(2025, 1, 1)
    )
    
    assert indexed_return == base_return


def test_apply_indexation_fixed(db_session: Session):
    """Test fixed indexation."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.06'),
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.FIXED,
        fixed_rate=Decimal('0.02'),  # 2% annual
        tax_treatment=TaxTreatment.TAXABLE
    )
    
    base_return = Decimal('500')
    # After 1 year with 2% indexation
    indexed_return = service.apply_indexation(
        base_return, asset, date(2025, 1, 1)
    )
    
    expected = base_return * Decimal('1.02')
    assert abs(indexed_return - expected) < Decimal('0.01')


def test_calculate_tax_exempt(db_session: Session):
    """Test tax calculation for exempt returns."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.SAVINGS_ACCOUNT,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.02'),
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.EXEMPT
    )
    
    tax_amount = service.calculate_tax(Decimal('500'), asset)
    assert tax_amount == Decimal('0')


def test_calculate_tax_fixed_rate(db_session: Session):
    """Test tax calculation for fixed rate."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('100000'),
        annual_return_rate=Decimal('0.06'),
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.15')  # 15%
    )
    
    tax_amount = service.calculate_tax(Decimal('500'), asset)
    assert tax_amount == Decimal('75')  # 500 * 0.15


def test_is_payment_date(db_session: Session):
    """Test payment date calculation."""
    service = CapitalAssetService()
    
    start_date = date(2024, 1, 1)
    
    # Monthly - every month is a payment date
    assert service._is_payment_date(date(2024, 1, 1), start_date, PaymentFrequency.MONTHLY) == True
    assert service._is_payment_date(date(2024, 2, 1), start_date, PaymentFrequency.MONTHLY) == True
    
    # Quarterly - every 3 months
    assert service._is_payment_date(date(2024, 1, 1), start_date, PaymentFrequency.QUARTERLY) == True
    assert service._is_payment_date(date(2024, 2, 1), start_date, PaymentFrequency.QUARTERLY) == False
    assert service._is_payment_date(date(2024, 4, 1), start_date, PaymentFrequency.QUARTERLY) == True
    
    # Annually - every 12 months
    assert service._is_payment_date(date(2024, 1, 1), start_date, PaymentFrequency.ANNUALLY) == True
    assert service._is_payment_date(date(2024, 6, 1), start_date, PaymentFrequency.ANNUALLY) == False
    assert service._is_payment_date(date(2025, 1, 1), start_date, PaymentFrequency.ANNUALLY) == True


def test_project_cashflow(db_session: Session):
    """Test cashflow projection."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('120000'),
        annual_return_rate=Decimal('0.05'),  # 5% annual
        payment_frequency=PaymentFrequency.QUARTERLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.20')
    )
    
    cashflow = service.project_cashflow(
        asset, 
        date(2024, 1, 1), 
        date(2024, 12, 31)
    )
    
    # Should have 4 quarterly payments
    assert len(cashflow) == 4
    
    # Check first item (quarterly return = 120000 * 0.05 / 4 = 1500)
    first_item = cashflow[0]
    assert first_item.date == date(2024, 1, 1)
    assert first_item.gross_return == Decimal('1500')
    assert first_item.tax_amount == Decimal('300')  # 1500 * 0.20
    assert first_item.net_return == Decimal('1200')  # 1500 - 300
    assert first_item.asset_type == AssetType.STOCKS


def test_generate_combined_cashflow(db_session: Session):
    """Test combined cashflow generation for multiple assets."""
    service = CapitalAssetService()
    
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Create two assets
    asset1 = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('60000'),
        annual_return_rate=Decimal('0.08'),  # 8% annual
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.EXEMPT
    )
    
    asset2 = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.BONDS,
        current_value=Decimal('40000'),
        annual_return_rate=Decimal('0.06'),  # 6% annual
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 29),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.25')
    )
    
    db_session.add_all([asset1, asset2])
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
    # Asset1: 60000 * 0.08 / 12 = 400 (exempt)
    # Asset2: 40000 * 0.06 / 12 = 200, tax = 50, net = 150
    first_month = combined_cashflow[0]
    assert first_month['date'] == date(2024, 1, 1)
    assert first_month['gross_return'] == Decimal('600')  # 400 + 200
    assert first_month['tax_amount'] == Decimal('50')     # 0 + 50
    assert first_month['net_return'] == Decimal('550')    # 400 + 150
