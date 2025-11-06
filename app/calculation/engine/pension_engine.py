"""
Pension Engine - Pension Conversion Calculations
=================================================

Handles conversion of capital amounts to monthly pension payments.
"""

from datetime import date
from typing import Dict, Any, Optional, List
from .base_engine import BaseEngine
from app.providers.tax_params import TaxParamsProvider
from app.schemas.tax import TaxParameters
from app.models.pension_fund import PensionFund


class PensionEngine(BaseEngine):
    """
    Engine for calculating monthly pension from capital.
    
    Converts lump sum capital amounts into monthly pension payments
    based on actuarial factors and tax parameters.
    """
    
    def __init__(self, tax_provider: TaxParamsProvider = None):
        """
        Initialize the pension engine.
        
        Args:
            tax_provider: Provider for tax parameters (optional)
        """
        super().__init__(db=None, tax_provider=tax_provider)
    
    @staticmethod
    def _calc_monthly_pension_from_capital(capital: float, params: TaxParameters) -> float:
        """Calculate monthly pension from capital using annuity factor"""
        if capital < 0:
            raise ValueError("הון פנסיוני שלילי אינו חוקי")
        return round(capital / params.annuity_factor, 2)
    
    @staticmethod
    def _calc_pension_from_fund(fund: PensionFund, params: TaxParameters) -> float:
        """Calculate pension amount from a pension fund based on its input mode"""
        if fund.input_mode == "manual":
            return float(fund.pension_amount or 0.0)
        
        # For calculated mode
        balance = float(fund.balance or 0.0)
        annuity_factor = float(fund.annuity_factor or params.annuity_factor)
        
        if annuity_factor <= 0:
            raise ValueError("מקדם המרה חייב להיות חיובי")
        
        return round(balance / annuity_factor, 2)
    
    @staticmethod
    def _apply_indexation(amount: float, method: str, start_date: date, 
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
    
    @staticmethod
    def _project_pension_cashflow(fund: PensionFund, months: int, 
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
                base_amount = PensionEngine._calc_pension_from_fund(fund, params)
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
                indexed_amount = PensionEngine._apply_indexation(
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
    
    def calculate(
        self, 
        capital: float, 
        params: Dict[str, Any] = None
    ) -> float:
        """
        Calculate monthly pension from capital amount.
        
        Args:
            capital: Capital amount to convert
            params: Tax parameters (optional, will fetch if not provided)
            
        Returns:
            Monthly pension amount
            
        Raises:
            ValueError: If capital is invalid
        """
        self.validate_inputs(capital=capital)
        
        # Get tax parameters if not provided
        if params is None and self.tax_provider is not None:
            params = self.tax_provider.get_params()
        
        # Calculate monthly pension
        monthly_pension = self._calc_monthly_pension_from_capital(capital, params)
        
        return round(monthly_pension, 2)
    
    def calculate_with_details(
        self,
        capital: float,
        params: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate pension with additional details.
        
        Args:
            capital: Capital amount to convert
            params: Tax parameters (optional)
            
        Returns:
            Dictionary containing:
                - monthly_pension: Monthly pension amount
                - annual_pension: Annual pension amount
                - capital: Original capital amount
        """
        monthly = self.calculate(capital, params)
        
        return {
            'monthly_pension': monthly,
            'annual_pension': round(monthly * 12, 2),
            'capital': round(capital, 2)
        }
    
    def validate_inputs(self, capital: float) -> bool:
        """
        Validate pension calculation inputs.
        
        Args:
            capital: Capital amount
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If capital is invalid
        """
        if capital < 0:
            raise ValueError("Capital cannot be negative")
        
        if not isinstance(capital, (int, float)):
            raise ValueError("Capital must be a numeric value")
        
        return True
