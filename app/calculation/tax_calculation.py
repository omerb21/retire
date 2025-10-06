"""
Tax calculation module for retirement planning system
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from datetime import date

def calculate_grant_tax(
    amount: Decimal, 
    service_years: float = None, 
    tax_rate: float = 0.25,
    max_exempt_per_year: Decimal = Decimal('12500')
) -> Dict[str, float]:
    """
    Calculate tax implications for a grant
    
    Args:
        amount: Grant amount
        service_years: Years of service (for severance grants)
        tax_rate: Tax rate for taxable amount (default 25%)
        max_exempt_per_year: Maximum exempt amount per year of service
        
    Returns:
        Dictionary with grant_exempt, grant_taxable, and tax_due
    """
    # Default values
    calculation = {
        "grant_exempt": 0.0,
        "grant_taxable": 0.0,
        "tax_due": 0.0
    }
    
    # Convert to Decimal for precise calculations
    amount_dec = Decimal(str(amount))
    
    if service_years and service_years > 0:
        # For severance grants, exempt amount is based on service years
        exempt_cap = max_exempt_per_year * Decimal(str(service_years))
        
        # Maximum total exemption is 375,000 NIS
        max_total_exemption = Decimal('375000')
        exempt_cap = min(exempt_cap, max_total_exemption)
        
        if amount_dec <= exempt_cap:
            calculation["grant_exempt"] = float(amount_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            calculation["grant_taxable"] = 0.0
            calculation["tax_due"] = 0.0
        else:
            calculation["grant_exempt"] = float(exempt_cap.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            taxable = amount_dec - exempt_cap
            calculation["grant_taxable"] = float(taxable.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            calculation["tax_due"] = float((taxable * Decimal(str(tax_rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    else:
        # For other grants, all amount is taxable
        calculation["grant_exempt"] = 0.0
        calculation["grant_taxable"] = float(amount_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        calculation["tax_due"] = float((amount_dec * Decimal(str(tax_rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    return calculation

def calculate_service_years(start_date: date, end_date: date) -> float:
    """
    Calculate years of service between two dates
    
    Args:
        start_date: Employment start date
        end_date: Employment end date
        
    Returns:
        Years of service as float with 2 decimal precision
    """
    if not start_date or not end_date:
        return 0.0
        
    # Calculate days between dates
    days = (end_date - start_date).days
    
    # Convert to years (365.25 days per year to account for leap years)
    years = days / 365.25
    
    # Round to 2 decimal places
    return round(years, 2)
