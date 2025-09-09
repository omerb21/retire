"""
Calculation Engine with stub functions for retirement planning calculations
"""
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal


def calculate_service_years(start_date: date, end_date: Optional[date] = None, 
                          non_continuous_periods: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    Calculate service years for an employee
    
    Args:
        start_date: Employment start date
        end_date: Employment end date (None if still employed)
        non_continuous_periods: List of non-continuous periods
        
    Returns:
        Dict with service years calculation details
    """
    if end_date is None:
        end_date = date.today()
    
    # Basic calculation - will be enhanced later
    total_days = (end_date - start_date).days
    service_years = round(total_days / 365.25, 2)
    
    # Subtract non-continuous periods (stub implementation)
    if non_continuous_periods:
        for period in non_continuous_periods:
            # This is a stub - real implementation would parse dates and subtract
            service_years -= 0.1  # Placeholder reduction
    
    return {
        "service_years": service_years,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_days": total_days,
        "non_continuous_periods": non_continuous_periods or [],
        "calculation_method": "basic_days_365"
    }


def apply_indexation(base_amount: Decimal, indexation_method: str = "none", 
                    fixed_rate: Optional[Decimal] = None, years: int = 1) -> Dict[str, Any]:
    """
    Apply indexation to a base amount
    
    Args:
        base_amount: Base amount to index
        indexation_method: Method of indexation (none, cpi, fixed)
        fixed_rate: Fixed indexation rate (if method is fixed)
        years: Number of years to apply indexation
        
    Returns:
        Dict with indexation calculation details
    """
    indexed_amount = base_amount
    
    if indexation_method == "fixed" and fixed_rate:
        # Apply compound interest
        indexed_amount = base_amount * ((1 + fixed_rate) ** years)
    elif indexation_method == "cpi":
        # Stub: Use fixed 2% CPI rate
        cpi_rate = Decimal("0.02")
        indexed_amount = base_amount * ((1 + cpi_rate) ** years)
    
    return {
        "base_amount": float(base_amount),
        "indexed_amount": float(indexed_amount),
        "indexation_method": indexation_method,
        "fixed_rate": float(fixed_rate) if fixed_rate else None,
        "years": years,
        "total_increase": float(indexed_amount - base_amount),
        "increase_percentage": float((indexed_amount - base_amount) / base_amount * 100) if base_amount > 0 else 0
    }


def calculate_severance_grant(salary: Decimal, service_years: Decimal, 
                            tax_params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Calculate severance grant amount and tax implications
    
    Args:
        salary: Monthly salary
        service_years: Years of service
        tax_params: Tax parameters for calculation
        
    Returns:
        Dict with severance calculation details
    """
    # Basic severance calculation: salary * service_years
    gross_severance = salary * service_years
    
    # Stub tax calculation
    exemption_cap = Decimal("400000")  # Example exemption cap
    taxable_amount = max(Decimal("0"), gross_severance - exemption_cap)
    tax_rate = Decimal("0.35")  # Example tax rate
    tax_due = taxable_amount * tax_rate
    net_severance = gross_severance - tax_due
    
    return {
        "gross_severance": float(gross_severance),
        "exemption_cap": float(exemption_cap),
        "exempt_amount": float(min(gross_severance, exemption_cap)),
        "taxable_amount": float(taxable_amount),
        "tax_rate": float(tax_rate),
        "tax_due": float(tax_due),
        "net_severance": float(net_severance),
        "salary": float(salary),
        "service_years": float(service_years),
        "calculation_method": "basic_salary_years"
    }


def calculate_pension_income(balance: Decimal, annuity_factor: Decimal,
                           indexation_method: str = "none", 
                           fixed_rate: Optional[Decimal] = None) -> Dict[str, Any]:
    """
    Calculate monthly pension income from pension fund
    
    Args:
        balance: Current pension fund balance
        annuity_factor: Annuity factor for conversion
        indexation_method: Method of indexation
        fixed_rate: Fixed indexation rate
        
    Returns:
        Dict with pension income calculation details
    """
    monthly_pension = balance * annuity_factor / 12
    
    # Apply indexation for future projections
    indexed_pension = monthly_pension
    if indexation_method == "fixed" and fixed_rate:
        # Assume 10 years projection
        indexed_pension = monthly_pension * ((1 + fixed_rate) ** 10)
    elif indexation_method == "cpi":
        # Stub: Use 2% CPI
        cpi_rate = Decimal("0.02")
        indexed_pension = monthly_pension * ((1 + cpi_rate) ** 10)
    
    return {
        "balance": float(balance),
        "annuity_factor": float(annuity_factor),
        "monthly_pension": float(monthly_pension),
        "annual_pension": float(monthly_pension * 12),
        "indexed_monthly_pension": float(indexed_pension),
        "indexed_annual_pension": float(indexed_pension * 12),
        "indexation_method": indexation_method,
        "fixed_rate": float(fixed_rate) if fixed_rate else None,
        "projection_years": 10
    }


def generate_cashflow(client_id: int, scenario_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate cashflow projection for a client scenario
    
    Args:
        client_id: Client ID
        scenario_params: Scenario parameters
        
    Returns:
        Dict with cashflow projection including monthly and yearly data
    """
    # Stub implementation - generates sample cashflow data
    monthly_data = []
    yearly_totals = {}
    
    # Generate 12 months of sample data
    base_income = Decimal("10000")
    base_expenses = Decimal("8000")
    
    for month in range(1, 13):
        month_date = f"2025-{month:02d}-01"
        
        # Add some variation
        income_variation = Decimal(str(month * 100))
        expense_variation = Decimal(str(month * 50))
        
        monthly_income = base_income + income_variation
        monthly_expenses = base_expenses + expense_variation
        net_cashflow = monthly_income - monthly_expenses
        
        monthly_data.append({
            "month": month,
            "date": month_date,
            "income": float(monthly_income),
            "expenses": float(monthly_expenses),
            "net": float(net_cashflow),
            "cumulative_net": float(net_cashflow * month)
        })
    
    # Calculate yearly totals
    total_income = sum(item["income"] for item in monthly_data)
    total_expenses = sum(item["expenses"] for item in monthly_data)
    total_net = sum(item["net"] for item in monthly_data)
    
    yearly_totals["2025"] = {
        "income": total_income,
        "expenses": total_expenses,
        "net": total_net
    }
    
    return {
        "client_id": client_id,
        "scenario_params": scenario_params,
        "monthly": monthly_data,
        "yearly_totals": yearly_totals,
        "projection_period": "2025",
        "calculation_date": datetime.now().isoformat(),
        "status": "completed"
    }
