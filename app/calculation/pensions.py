from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from app.schemas.tax import TaxParameters
from app.models.pension_fund import PensionFund

def calc_monthly_pension_from_capital(capital: float, params: TaxParameters) -> float:
    """Calculate monthly pension from capital using annuity factor"""
    if capital < 0:
        raise ValueError("הון פנסיוני שלילי אינו חוקי")
    return round(capital / params.annuity_factor, 2)

def calc_pension_from_fund(fund: PensionFund, params: TaxParameters) -> float:
    """Calculate pension amount from a pension fund based on its input mode"""
    if fund.input_mode == "manual":
        return float(fund.pension_amount or 0.0)
    
    # For calculated mode
    balance = float(fund.balance or 0.0)
    annuity_factor = float(fund.annuity_factor or params.annuity_factor)
    
    if annuity_factor <= 0:
        raise ValueError("מקדם המרה חייב להיות חיובי")
        
    return round(balance / annuity_factor, 2)

def apply_indexation(amount: float, method: str, start_date: date, 
                     reference_date: Optional[date] = None, 
                     fixed_rate: Optional[float] = None,
                     params: Optional[TaxParameters] = None) -> float:
    """Apply indexation to a pension amount based on method"""
    if amount <= 0 or not start_date:
        return amount
        
    today = reference_date or date.today()
    
    # No indexation
    if method == "none":
        return amount
        
    # Fixed rate indexation
    if method == "fixed" and fixed_rate is not None:
        # Calculate years difference including partial years
        years_diff = (today.year - start_date.year) + (today.month - start_date.month) / 12
        indexed = amount * ((1 + fixed_rate) ** years_diff)
        return round(indexed, 2)
        
    # CPI indexation
    if method == "cpi" and params and hasattr(params, "cpi_series"):
        try:
            # Get CPI values for start and reference dates
            start_key = date(start_date.year, start_date.month, 1)
            ref_key = date(today.year, today.month, 1)
            
            start_cpi = params.cpi_series.get(start_key)
            ref_cpi = params.cpi_series.get(ref_key)
            
            if start_cpi and ref_cpi and start_cpi > 0:
                factor = ref_cpi / start_cpi
                return round(amount * factor, 2)
        except (KeyError, AttributeError):
            pass
            
    # Default: return original amount if indexation cannot be applied
    return amount

def project_pension_cashflow(fund: PensionFund, months: int, 
                            params: Optional[TaxParameters] = None,
                            reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Project pension cashflow for a number of months"""
    if not fund.pension_amount and not fund.balance:
        return []
        
    start_date = reference_date or date.today()
    cashflow = []
    
    # Calculate base pension amount
    if fund.input_mode == "manual":
        base_amount = float(fund.pension_amount or 0.0)
    else:
        # Use params if provided, otherwise use fund's annuity factor
        if params:
            base_amount = calc_pension_from_fund(fund, params)
        else:
            balance = float(fund.balance or 0.0)
            annuity_factor = float(fund.annuity_factor or 0.0)
            if annuity_factor <= 0:
                return []
            base_amount = round(balance / annuity_factor, 2)
    
    # Generate cashflow for each month
    current_date = start_date
    for i in range(months):
        # Calculate indexed amount for this month
        if fund.indexation_method == "none":
            indexed_amount = base_amount
        elif fund.indexation_method == "fixed" and fund.fixed_index_rate is not None:
            # Apply compound interest for each month
            years = i / 12  # Convert months to years
            indexed_amount = base_amount * ((1 + fund.fixed_index_rate) ** years)
        elif fund.indexation_method == "cpi" and params and hasattr(params, "cpi_series"):
            # Apply CPI indexation if possible
            indexed_amount = apply_indexation(
                base_amount, 
                "cpi", 
                fund.pension_start_date or start_date, 
                current_date, 
                None, 
                params
            )
        else:
            indexed_amount = base_amount
        
        # Add to cashflow
        cashflow.append({
            "date": current_date,
            "amount": round(indexed_amount, 2),
            "fund_name": fund.fund_name,
            "fund_id": fund.id
        })
        
        # Move to next month
        month = current_date.month + 1
        year = current_date.year
        if month > 12:
            month = 1
            year += 1
        current_date = date(year, month, 1)
    
    return cashflow
