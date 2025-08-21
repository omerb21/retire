"""Tests for Income Integration functions."""

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome, IncomeSourceType, PaymentFrequency, IndexationMethod, TaxTreatment
from app.models.capital_asset import CapitalAsset, AssetType
from app.models.client import Client
from app.calculation.income_integration import (
    integrate_additional_incomes_with_scenario,
    integrate_capital_assets_with_scenario,
    integrate_all_incomes_with_scenario
)


def test_integrate_additional_incomes_with_scenario(db_session: Session):
    """Test integration of additional incomes with scenario cashflow."""
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Create additional income
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('3000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.30')
    )
    db_session.add(income)
    db_session.commit()
    
    # Sample scenario cashflow
    scenario_cashflow = [
        {
            'date': date(2024, 1, 1),
            'inflow': 10000.0,
            'outflow': 8000.0,
            'net': 2000.0
        },
        {
            'date': date(2024, 2, 1),
            'inflow': 10000.0,
            'outflow': 8000.0,
            'net': 2000.0
        }
    ]
    
    # Integrate additional incomes
    integrated = integrate_additional_incomes_with_scenario(
        db_session, client.id, scenario_cashflow, date(2024, 1, 1)
    )
    
    # Verify integration
    assert len(integrated) == 2
    
    # Check first month
    first_month = integrated[0]
    assert first_month['date'] == date(2024, 1, 1)
    assert first_month['additional_income_gross'] == 3000.0
    assert first_month['additional_income_tax'] == 900.0  # 3000 * 0.30
    assert first_month['additional_income_net'] == 2100.0  # 3000 - 900
    assert first_month['inflow'] == 12100.0  # 10000 + 2100
    assert first_month['net'] == 4100.0  # 2000 + 2100


def test_integrate_capital_assets_with_scenario(db_session: Session):
    """Test integration of capital assets with scenario cashflow."""
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Create capital asset
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.STOCKS,
        current_value=Decimal('120000'),
        annual_return_rate=Decimal('0.06'),  # 6% annual
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.25')
    )
    db_session.add(asset)
    db_session.commit()
    
    # Sample scenario cashflow
    scenario_cashflow = [
        {
            'date': date(2024, 1, 1),
            'inflow': 10000.0,
            'outflow': 8000.0,
            'net': 2000.0
        },
        {
            'date': date(2024, 2, 1),
            'inflow': 10000.0,
            'outflow': 8000.0,
            'net': 2000.0
        }
    ]
    
    # Integrate capital assets
    integrated = integrate_capital_assets_with_scenario(
        db_session, client.id, scenario_cashflow, date(2024, 1, 1)
    )
    
    # Verify integration
    assert len(integrated) == 2
    
    # Check first month (monthly return = 120000 * 0.06 / 12 = 600)
    first_month = integrated[0]
    assert first_month['date'] == date(2024, 1, 1)
    assert first_month['capital_return_gross'] == 600.0
    assert first_month['capital_return_tax'] == 150.0  # 600 * 0.25
    assert first_month['capital_return_net'] == 450.0  # 600 - 150
    assert first_month['inflow'] == 10450.0  # 10000 + 450
    assert first_month['net'] == 2450.0  # 2000 + 450


def test_integrate_all_incomes_with_scenario(db_session: Session):
    """Test integration of both additional incomes and capital assets."""
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Create additional income
    income = AdditionalIncome(
        client_id=client.id,
        source_type=IncomeSourceType.RENTAL,
        amount=Decimal('2000'),
        frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.EXEMPT
    )
    
    # Create capital asset
    asset = CapitalAsset(
        client_id=client.id,
        asset_type=AssetType.BONDS,
        current_value=Decimal('60000'),
        annual_return_rate=Decimal('0.04'),  # 4% annual
        payment_frequency=PaymentFrequency.MONTHLY,
        start_date=date(2024, 1, 1),
        indexation_method=IndexationMethod.NONE,
        tax_treatment=TaxTreatment.FIXED_RATE,
        tax_rate=Decimal('0.20')
    )
    
    db_session.add_all([income, asset])
    db_session.commit()
    
    # Sample scenario cashflow
    scenario_cashflow = [
        {
            'date': date(2024, 1, 1),
            'inflow': 5000.0,
            'outflow': 4000.0,
            'net': 1000.0
        }
    ]
    
    # Integrate all income sources
    integrated = integrate_all_incomes_with_scenario(
        db_session, client.id, scenario_cashflow, date(2024, 1, 1)
    )
    
    # Verify integration
    assert len(integrated) == 1
    
    # Check totals
    # Additional income: 2000 (exempt, no tax)
    # Capital asset: 60000 * 0.04 / 12 = 200, tax = 40, net = 160
    first_month = integrated[0]
    assert first_month['date'] == date(2024, 1, 1)
    
    # Additional income fields
    assert first_month['additional_income_gross'] == 2000.0
    assert first_month['additional_income_tax'] == 0.0
    assert first_month['additional_income_net'] == 2000.0
    
    # Capital asset fields
    assert first_month['capital_return_gross'] == 200.0
    assert first_month['capital_return_tax'] == 40.0
    assert first_month['capital_return_net'] == 160.0
    
    # Total inflow and net
    assert first_month['inflow'] == 7160.0  # 5000 + 2000 + 160
    assert first_month['net'] == 3160.0  # 1000 + 2000 + 160


def test_integrate_with_empty_scenario(db_session: Session):
    """Test integration with empty scenario cashflow."""
    # Create test client
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Empty scenario cashflow
    scenario_cashflow = []
    
    # Should return empty list
    integrated = integrate_additional_incomes_with_scenario(
        db_session, client.id, scenario_cashflow
    )
    
    assert integrated == []


def test_integrate_with_no_income_sources(db_session: Session):
    """Test integration when client has no income sources."""
    # Create test client with no income sources
    client = Client(first_name="Test", last_name="User", id_number="123456789")
    db_session.add(client)
    db_session.flush()
    
    # Sample scenario cashflow
    scenario_cashflow = [
        {
            'date': date(2024, 1, 1),
            'inflow': 5000.0,
            'outflow': 4000.0,
            'net': 1000.0
        }
    ]
    
    # Integrate (should add zero amounts)
    integrated = integrate_additional_incomes_with_scenario(
        db_session, client.id, scenario_cashflow
    )
    
    # Should have same structure but with zero income amounts
    assert len(integrated) == 1
    first_month = integrated[0]
    assert first_month['additional_income_gross'] == 0.0
    assert first_month['additional_income_tax'] == 0.0
    assert first_month['additional_income_net'] == 0.0
    assert first_month['inflow'] == 5000.0  # unchanged
    assert first_month['net'] == 1000.0  # unchanged
