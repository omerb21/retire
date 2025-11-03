"""
Seniority Engine - Tenure Calculations
=======================================

Handles calculation of years of service/seniority.
"""

from datetime import date
from typing import Optional
from .base_engine import BaseEngine
from app.calculation.seniority import calc_seniority_years


class SeniorityEngine(BaseEngine):
    """
    Engine for calculating years of seniority/tenure.
    
    Uses the existing seniority calculation module.
    """
    
    def __init__(self):
        """Initialize the seniority engine (no dependencies needed)."""
        super().__init__(db=None, tax_provider=None)
    
    def calculate(self, start_date: date, end_date: Optional[date] = None) -> float:
        """
        Calculate years of seniority between two dates.
        
        Args:
            start_date: Employment start date
            end_date: Employment end date (defaults to today if None)
            
        Returns:
            Years of seniority as a float
            
        Raises:
            ValueError: If start_date is after end_date
        """
        if end_date is None:
            end_date = date.today()
        
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
        
        return calc_seniority_years(start_date, end_date)
    
    def validate_inputs(self, start_date: date, end_date: Optional[date] = None) -> bool:
        """
        Validate seniority calculation inputs.
        
        Args:
            start_date: Employment start date
            end_date: Employment end date
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not isinstance(start_date, date):
            raise ValueError("start_date must be a date object")
        
        if end_date is not None and not isinstance(end_date, date):
            raise ValueError("end_date must be a date object or None")
        
        effective_end = end_date or date.today()
        if start_date > effective_end:
            raise ValueError("Start date cannot be after end date")
        
        return True
