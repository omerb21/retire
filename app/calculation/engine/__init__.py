"""
Engine Package - Modular Calculation Engines
=============================================

This package contains specialized calculation engines for different aspects
of retirement planning calculations.

Modules:
- base_engine: Abstract base class for all engines
- seniority_engine: Seniority/tenure calculations
- grant_engine: Grant and severance calculations with indexation
- pension_engine: Pension conversion calculations
- cashflow_engine: Cashflow projection generation
"""

from .base_engine import BaseEngine
from .seniority_engine import SeniorityEngine
from .grant_engine import GrantEngine
from .pension_engine import PensionEngine
from .cashflow_engine import CashflowEngine

__all__ = [
    'BaseEngine',
    'SeniorityEngine',
    'GrantEngine',
    'PensionEngine',
    'CashflowEngine'
]
