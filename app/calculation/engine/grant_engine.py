"""
Grant Engine - Severance Grant Calculations
============================================

Handles calculation of severance grants including indexation and tax components.
"""

from datetime import date
from typing import Dict, Any
from decimal import Decimal
from .base_engine import BaseEngine
from app.providers.tax_params import TaxParamsProvider
from app.calculation.indexation import index_factor, index_amount
from app.calculation.grants import calc_grant_components


class GrantEngine(BaseEngine):
    """
    Engine for calculating severance grants.
    
    Handles:
    - Indexation of base amounts
    - Tax-exempt and taxable components
    - Tax calculation
    - Net grant amount
    """
    
    def __init__(self, tax_provider: TaxParamsProvider):
        """
        Initialize the grant engine.
        
        Args:
            tax_provider: Provider for tax parameters
        """
        super().__init__(db=None, tax_provider=tax_provider)
    
    def calculate(
        self, 
        base_amount: float, 
        start_date: date, 
        end_date: date,
        params: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate grant components including indexation and tax.
        
        Args:
            base_amount: Base grant amount before indexation
            start_date: Employment start date
            end_date: Employment end date or calculation date
            params: Tax parameters (optional, will fetch if not provided)
            
        Returns:
            Dictionary containing:
                - gross: Indexed gross amount
                - exempt: Tax-exempt portion
                - taxable: Taxable portion
                - tax: Tax amount
                - net: Net amount after tax
                - indexation_factor: Indexation factor applied
                
        Raises:
            ValueError: If inputs are invalid
        """
        self.validate_inputs(
            base_amount=base_amount,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get tax parameters if not provided
        if params is None:
            params = self.tax_provider.get_params()
        
        # Calculate indexation
        f = index_factor(params, start_date, end_date)
        indexed_amount = index_amount(base_amount, f)
        
        # Calculate grant components (exempt, taxable, tax)
        exempt, taxable, tax = calc_grant_components(indexed_amount, params)
        
        # Calculate net amount
        net_amount = indexed_amount - tax
        
        return {
            'gross': round(indexed_amount, 2),
            'exempt': round(exempt, 2),
            'taxable': round(taxable, 2),
            'tax': round(tax, 2),
            'net': round(net_amount, 2),
            'indexation_factor': round(f, 4)
        }
    
    def calculate_indexation_only(
        self,
        base_amount: float,
        start_date: date,
        end_date: date,
        params: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Calculate only the indexation without tax components.
        
        Args:
            base_amount: Base amount before indexation
            start_date: Start date for indexation
            end_date: End date for indexation
            params: Tax parameters (optional)
            
        Returns:
            Dictionary with indexed_amount and indexation_factor
        """
        if params is None:
            params = self.tax_provider.get_params()
        
        f = index_factor(params, start_date, end_date)
        indexed_amount = index_amount(base_amount, f)
        
        return {
            'indexed_amount': round(indexed_amount, 2),
            'indexation_factor': round(f, 4)
        }
    
    def validate_inputs(
        self,
        base_amount: float,
        start_date: date,
        end_date: date
    ) -> bool:
        """
        Validate grant calculation inputs.
        
        Args:
            base_amount: Base grant amount
            start_date: Employment start date
            end_date: Employment end date
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If inputs are invalid
        """
        if base_amount <= 0:
            raise ValueError("Base amount must be positive")
        
        if not isinstance(start_date, date):
            raise ValueError("start_date must be a date object")
        
        if not isinstance(end_date, date):
            raise ValueError("end_date must be a date object")
        
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
        
        return True
