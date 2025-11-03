"""
Cashflow Engine - Cashflow Projection Generation
=================================================

Handles generation of cashflow projections for retirement planning.
"""

from datetime import date
from typing import List, Dict, Any
from .base_engine import BaseEngine
from app.calculation.cashflow import make_simple_cashflow


class CashflowEngine(BaseEngine):
    """
    Engine for generating cashflow projections.
    
    Creates monthly or annual cashflow projections based on
    income and expense parameters.
    """
    
    def __init__(self):
        """Initialize the cashflow engine (no dependencies needed)."""
        super().__init__(db=None, tax_provider=None)
    
    def calculate(
        self,
        start_date: date,
        months: int,
        income: float,
        expense: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Generate cashflow projection.
        
        Args:
            start_date: Start date for cashflow
            months: Number of months to project
            income: Monthly income amount
            expense: Monthly expense amount (default: 0.0)
            
        Returns:
            List of cashflow items, each containing date and amounts
            
        Raises:
            ValueError: If inputs are invalid
        """
        self.validate_inputs(
            start_date=start_date,
            months=months,
            income=income,
            expense=expense
        )
        
        return make_simple_cashflow(start_date, months, income, expense)
    
    def calculate_net_cashflow(
        self,
        start_date: date,
        months: int,
        income: float,
        expense: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate cashflow with summary statistics.
        
        Args:
            start_date: Start date for cashflow
            months: Number of months to project
            income: Monthly income amount
            expense: Monthly expense amount
            
        Returns:
            Dictionary containing:
                - cashflow: List of cashflow items
                - total_income: Total income over period
                - total_expense: Total expenses over period
                - net_cashflow: Net cashflow (income - expense)
        """
        cashflow = self.calculate(start_date, months, income, expense)
        
        total_income = income * months
        total_expense = expense * months
        net = total_income - total_expense
        
        return {
            'cashflow': cashflow,
            'total_income': round(total_income, 2),
            'total_expense': round(total_expense, 2),
            'net_cashflow': round(net, 2),
            'months': months
        }
    
    def validate_inputs(
        self,
        start_date: date,
        months: int,
        income: float,
        expense: float
    ) -> bool:
        """
        Validate cashflow calculation inputs.
        
        Args:
            start_date: Start date
            months: Number of months
            income: Monthly income
            expense: Monthly expense
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not isinstance(start_date, date):
            raise ValueError("start_date must be a date object")
        
        if months <= 0:
            raise ValueError("months must be positive")
        
        if not isinstance(months, int):
            raise ValueError("months must be an integer")
        
        if income < 0:
            raise ValueError("income cannot be negative")
        
        if expense < 0:
            raise ValueError("expense cannot be negative")
        
        return True
