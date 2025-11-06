from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.pension_fund import PensionFund
from app.models.client import Client
from app.schemas.tax import TaxParameters
from app.calculation.engine.pension_engine import PensionEngine
from app.providers.tax_params import TaxParamsProvider, InMemoryTaxParamsProvider

def get_client_pension_funds(db: Session, client_id: int) -> List[PensionFund]:
    """Get all pension funds for a client"""
    return db.query(PensionFund).filter(PensionFund.client_id == client_id).all()

def calculate_total_monthly_pension(funds: List[PensionFund], 
                                   params: Optional[TaxParameters] = None,
                                   reference_date: Optional[date] = None) -> float:
    """Calculate total monthly pension from all funds"""
    if not funds:
        return 0.0
        
    # Get tax parameters if not provided
    if not params:
        tax_provider = InMemoryTaxParamsProvider()
        params = tax_provider.get_params()
    
    total = 0.0
    for fund in funds:
        # For manual input mode, use the indexed_pension_amount if available
        if fund.input_mode == "manual" and fund.indexed_pension_amount is not None:
            total += fund.indexed_pension_amount
        # For manual input mode without indexed amount, use pension_amount
        elif fund.input_mode == "manual" and fund.pension_amount is not None:
            total += fund.pension_amount
        # For calculated mode, calculate from balance and annuity factor
        else:
            try:
                pension = PensionEngine._calc_pension_from_fund(fund, params)
                total += pension
            except (ValueError, ZeroDivisionError):
                # Skip funds with invalid calculation parameters
                continue
                
    return round(total, 2)

def generate_combined_pension_cashflow(db: Session, 
                                      client_id: int, 
                                      months: int = 12,
                                      reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Generate combined pension cashflow for all client's pension funds"""
    # Get client's pension funds
    funds = get_client_pension_funds(db, client_id)
    if not funds:
        return []
        
    # Get tax parameters for calculations
    tax_provider = InMemoryTaxParamsProvider()
    params = tax_provider.get_params()
    
    # Generate cashflow for each fund
    start_date = reference_date or date.today()
    all_cashflows = []
    
    for fund in funds:
        fund_cashflow = PensionEngine._project_pension_cashflow(fund, months, params, start_date)
        all_cashflows.extend(fund_cashflow)
    
    # Organize by date
    combined_cashflow = {}
    for cf in all_cashflows:
        cf_date = cf["date"]
        if cf_date not in combined_cashflow:
            combined_cashflow[cf_date] = {
                "date": cf_date,
                "total_amount": 0.0,
                "funds": []
            }
        
        combined_cashflow[cf_date]["total_amount"] += cf["amount"]
        combined_cashflow[cf_date]["funds"].append({
            "fund_id": cf["fund_id"],
            "fund_name": cf["fund_name"],
            "amount": cf["amount"]
        })
    
    # Convert to sorted list
    result = list(combined_cashflow.values())
    result.sort(key=lambda x: x["date"])
    
    # Round total amounts
    for item in result:
        item["total_amount"] = round(item["total_amount"], 2)
    
    return result

def integrate_pension_funds_with_scenario(db: Session, 
                                         client_id: int,
                                         scenario_cashflow: List[Dict[str, Any]],
                                         reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Integrate pension funds cashflow with scenario cashflow"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get pension cashflow for the same period as scenario cashflow
    months = len(scenario_cashflow)
    pension_cashflow = generate_combined_pension_cashflow(db, client_id, months, reference_date)
    
    # Debug: Log pension cashflow
    logger.info(f"Generated pension cashflow: {pension_cashflow}")
    
    # Map pension cashflow by date
    pension_by_date = {cf["date"].isoformat(): cf for cf in pension_cashflow}
    logger.info(f"Pension by date keys: {list(pension_by_date.keys())}")
    
    # Integrate with scenario cashflow
    integrated_cashflow = []
    for sc_item in scenario_cashflow:
        sc_date = sc_item["date"]
        date_key = sc_date.isoformat()
        logger.info(f"Processing scenario date: {date_key}")
        
        # Create new integrated item
        integrated_item = {
            "date": sc_date,
            "inflow": sc_item.get("inflow", 0.0),
            "outflow": sc_item.get("outflow", 0.0),
            "net": sc_item.get("net", 0.0),
            "pension_income": 0.0,
            "pension_funds": []
        }
        
        # Add pension data if available for this date
        if date_key in pension_by_date:
            logger.info(f"Found matching pension data for date {date_key}")
            pension_data = pension_by_date[date_key]
            integrated_item["pension_income"] = pension_data["total_amount"]
            integrated_item["pension_funds"] = pension_data["funds"]
            
            # Update inflow and net with pension income
            integrated_item["inflow"] += pension_data["total_amount"]
            integrated_item["net"] += pension_data["total_amount"]
        else:
            logger.info(f"No pension data found for date {date_key}")
        
        integrated_cashflow.append(integrated_item)
    
    return integrated_cashflow
