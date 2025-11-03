"""
Pension Engine - Pension Conversion Calculations
=================================================

Handles conversion of capital amounts to monthly pension payments.
"""

from typing import Dict, Any
from .base_engine import BaseEngine
from app.providers.tax_params import TaxParamsProvider
from app.calculation.pensions import calc_monthly_pension_from_capital


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
        monthly_pension = calc_monthly_pension_from_capital(capital, params)
        
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
