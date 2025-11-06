"""
Calculation Engine - Main orchestrator for retirement calculations
===================================================================

This module provides the main CalculationEngine class that orchestrates
all calculation components for retirement planning scenarios.
"""

from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import Client, Employment
from app.providers.tax_params import TaxParamsProvider
from app.schemas.scenario import ScenarioIn, ScenarioOut
from app.calculation.seniority import calc_seniority_years
from app.calculation.indexation import index_factor, index_amount
from app.calculation.engine.grant_engine import GrantEngine
from app.calculation.engine.pension_engine import PensionEngine
from app.calculation.cashflow import make_simple_cashflow


class CalculationEngine:
    """
    Main calculation engine that orchestrates retirement planning calculations.
    
    This engine combines seniority, grants, pensions, and cashflow calculations
    to produce complete retirement scenarios.
    
    Attributes:
        db (Session): Database session for data access
        tax_provider (TaxParamsProvider): Provider for tax parameters
    """
    
    def __init__(self, db: Session, tax_provider: TaxParamsProvider):
        """
        Initialize the calculation engine.
        
        Args:
            db: SQLAlchemy database session
            tax_provider: Tax parameters provider instance
        """
        self.db = db
        self.tax_provider = tax_provider

    def run(self, client_id: int, scenario: ScenarioIn) -> ScenarioOut:
        """
        Execute a complete retirement scenario calculation.
        
        This method:
        1. Validates client and employment data
        2. Calculates seniority years
        3. Computes grant amounts with indexation
        4. Calculates tax components
        5. Determines pension amounts
        6. Generates cashflow projections
        
        Args:
            client_id: ID of the client
            scenario: Scenario input parameters
            
        Returns:
            ScenarioOut: Complete calculation results
            
        Raises:
            ValueError: If client not found, inactive, or missing employment data
        """
        # Validate client
        client = self.db.get(Client, client_id)
        if not client:
            raise ValueError("לקוח לא נמצא")
        if not client.is_active:
            raise ValueError("לקוח לא פעיל")

        # Get current employment
        employment = self.db.query(Employment).filter(
            Employment.client_id == client_id,
            Employment.is_current == True
        ).first()
        
        if not employment:
            raise ValueError("לא נמצאה תעסוקה נוכחית")

        # Get tax parameters
        params = self.tax_provider.get_params()
        
        # 1) Calculate seniority
        end_for_seniority = scenario.planned_termination_date or date.today()
        seniority = calc_seniority_years(employment.start_date, end_for_seniority)

        # 2) Calculate indexed grant amount
        # Note: Using base amount of 100,000 for demonstration
        base_amount = 100_000.0
        f = index_factor(params, employment.start_date, end_for_seniority)
        indexed_amount = index_amount(base_amount, f)

        # 3) Calculate grant components (exempt/taxable/tax)
        exempt, taxable, tax = GrantEngine._calc_grant_components(indexed_amount, params)
        grant_net = round(indexed_amount - tax, 2)

        # 4) Calculate monthly pension
        # Assumption: Converting net grant to monthly pension
        pension_monthly = PensionEngine._calc_monthly_pension_from_capital(grant_net, params)

        # 5) Generate cashflow (simple: 12 months ahead)
        income = scenario.other_incomes_monthly or pension_monthly
        expense = scenario.monthly_expenses or 0.0
        cashflow = make_simple_cashflow(end_for_seniority, 12, income, expense)

        return ScenarioOut(
            seniority_years=seniority,
            grant_gross=round(indexed_amount, 2),
            grant_exempt=exempt,
            grant_tax=tax,
            grant_net=grant_net,
            pension_monthly=pension_monthly,
            indexation_factor=f,
            cashflow=cashflow,
        )
