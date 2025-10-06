"""Integration functions for additional incomes and capital assets with scenario cashflow."""

import logging
from datetime import date
from typing import List, Optional, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services.additional_income_service import AdditionalIncomeService
from app.services.capital_asset_service import CapitalAssetService
from app.providers.tax_params import InMemoryTaxParamsProvider

logger = logging.getLogger(__name__)


def integrate_additional_incomes_with_scenario(
    db_session: Session,
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Integrate additional incomes with scenario cashflow.
    
    Args:
        db_session: Database session
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with additional income integrated
    """
    logger.debug(f"Integrating additional incomes for client {client_id}")
    
    if not scenario_cashflow:
        logger.debug("No scenario cashflow provided")
        return []
    
    # Set reference date to first day of month if not provided
    if reference_date is None:
        today = date.today()
        reference_date = date(today.year, today.month, 1)
    
    # Get date range from scenario
    start_date = min(item['date'] for item in scenario_cashflow)
    end_date = max(item['date'] for item in scenario_cashflow)
    
    logger.debug(f"Generating additional income cashflow from {start_date} to {end_date}")
    
    # Generate additional income cashflow
    income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
    income_cashflow = income_service.generate_combined_cashflow(
        db_session, client_id, start_date, end_date, reference_date
    )
    
    # Create a map of income by date for efficient lookup
    income_by_date = {item['date']: item for item in income_cashflow}
    
    # Integrate with scenario cashflow
    integrated_cashflow = []
    for scenario_item in scenario_cashflow:
        scenario_date = scenario_item['date']
        
        # Copy scenario item
        integrated_item = scenario_item.copy()
        
        # Add additional income fields
        if scenario_date in income_by_date:
            income_item = income_by_date[scenario_date]
            integrated_item['additional_income_gross'] = float(income_item['gross_amount'])
            integrated_item['additional_income_tax'] = float(income_item['tax_amount'])
            integrated_item['additional_income_net'] = float(income_item['net_amount'])
            
            # Update total inflow and net
            integrated_item['inflow'] = float(Decimal(str(integrated_item['inflow'])) + income_item['net_amount'])
            integrated_item['net'] = float(Decimal(str(integrated_item['net'])) + income_item['net_amount'])
        else:
            integrated_item['additional_income_gross'] = 0.0
            integrated_item['additional_income_tax'] = 0.0
            integrated_item['additional_income_net'] = 0.0
        
        integrated_cashflow.append(integrated_item)
    
    logger.debug(f"Integrated additional incomes into {len(integrated_cashflow)} cashflow items")
    return integrated_cashflow


def integrate_capital_assets_with_scenario(
    db_session: Session,
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Integrate capital assets with scenario cashflow.
    
    Args:
        db_session: Database session
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with capital asset returns integrated
    """
    logger.debug(f"Integrating capital assets for client {client_id}")
    
    if not scenario_cashflow:
        logger.debug("No scenario cashflow provided")
        return []
    
    # Set reference date to first day of month if not provided
    if reference_date is None:
        today = date.today()
        reference_date = date(today.year, today.month, 1)
    
    # Get date range from scenario
    start_date = min(item['date'] for item in scenario_cashflow)
    end_date = max(item['date'] for item in scenario_cashflow)
    
    logger.debug(f"Generating capital asset cashflow from {start_date} to {end_date}")
    
    # Generate capital asset cashflow
    asset_service = CapitalAssetService(InMemoryTaxParamsProvider())
    asset_cashflow = asset_service.generate_combined_cashflow(
        db_session, client_id, start_date, end_date, reference_date
    )
    
    # Create a map of asset returns by date for efficient lookup
    asset_by_date = {item['date']: item for item in asset_cashflow}
    
    # Integrate with scenario cashflow
    integrated_cashflow = []
    for scenario_item in scenario_cashflow:
        scenario_date = scenario_item['date']
        
        # Copy scenario item
        integrated_item = scenario_item.copy()
        
        # Add capital asset fields
        if scenario_date in asset_by_date:
            asset_item = asset_by_date[scenario_date]
            integrated_item['capital_return_gross'] = float(asset_item['gross_return'])
            integrated_item['capital_return_tax'] = float(asset_item['tax_amount'])
            integrated_item['capital_return_net'] = float(asset_item['net_return'])
            
            # Update total inflow and net
            integrated_item['inflow'] = float(Decimal(str(integrated_item['inflow'])) + asset_item['net_return'])
            integrated_item['net'] = float(Decimal(str(integrated_item['net'])) + asset_item['net_return'])
        else:
            integrated_item['capital_return_gross'] = 0.0
            integrated_item['capital_return_tax'] = 0.0
            integrated_item['capital_return_net'] = 0.0
        
        integrated_cashflow.append(integrated_item)
    
    logger.debug(f"Integrated capital assets into {len(integrated_cashflow)} cashflow items")
    return integrated_cashflow


def integrate_all_incomes_with_scenario(
    db_session: Session,
    client_id: int,
    scenario_cashflow: List[Dict[str, Any]],
    reference_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Integrate both additional incomes and capital assets with scenario cashflow.
    
    Args:
        db_session: Database session
        client_id: Client ID
        scenario_cashflow: List of scenario cashflow items with date, inflow, outflow, net
        reference_date: Reference date for calculations (defaults to first day of current month)
        
    Returns:
        Updated scenario cashflow with all income sources integrated
    """
    logger.debug(f"Integrating all income sources for client {client_id}")
    
    # First integrate additional incomes
    cashflow_with_incomes = integrate_additional_incomes_with_scenario(
        db_session, client_id, scenario_cashflow, reference_date
    )
    
    # Then integrate capital assets
    fully_integrated_cashflow = integrate_capital_assets_with_scenario(
        db_session, client_id, cashflow_with_incomes, reference_date
    )
    
    logger.debug(f"Fully integrated cashflow with {len(fully_integrated_cashflow)} items")
    return fully_integrated_cashflow
