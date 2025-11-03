"""
Calculation Engine V2 - Modular Refactored Version
===================================================

This is the refactored version of the calculation engine using modular components.
The original engine.py remains unchanged for backward compatibility.

Usage:
    from app.calculation.engine_v2 import CalculationEngineV2
    
    engine = CalculationEngineV2(db, tax_provider)
    result = engine.run(client_id, scenario)
"""

from datetime import date
from sqlalchemy.orm import Session
from app.models import Client, Employment
from app.providers.tax_params import TaxParamsProvider
from app.schemas.scenario import ScenarioIn, ScenarioOut
from .engine_factory import EngineFactory


class CalculationEngineV2:
    """
    Refactored calculation engine using modular components.
    
    This version splits responsibilities across specialized engines:
    - SeniorityEngine: Tenure calculations
    - GrantEngine: Severance grant calculations
    - PensionEngine: Pension conversion calculations
    - CashflowEngine: Cashflow projections
    """
    
    def __init__(self, db: Session, tax_provider: TaxParamsProvider):
        """
        Initialize the calculation engine.
        
        Args:
            db: Database session
            tax_provider: Tax parameters provider
        """
        self.db = db
        self.tax_provider = tax_provider
        self.engines = EngineFactory.create_engines(db, tax_provider)
    
    def _get_client(self, client_id: int) -> Client:
        """
        Retrieve and validate client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Client instance
            
        Raises:
            ValueError: If client not found or inactive
        """
        client = self.db.get(Client, client_id)
        if not client:
            raise ValueError("לקוח לא נמצא")
        if not client.is_active:
            raise ValueError("לקוח לא פעיל")
        return client
    
    def _get_current_employment(self, client_id: int) -> Employment:
        """
        Retrieve current employment for client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Employment instance
            
        Raises:
            ValueError: If no current employment found
        """
        employment = self.db.query(Employment).filter(
            Employment.client_id == client_id,
            Employment.is_current == True
        ).first()
        
        if not employment:
            raise ValueError("לא נמצאה תעסוקה נוכחית")
        
        return employment
    
    def run(self, client_id: int, scenario: ScenarioIn) -> ScenarioOut:
        """
        Run the complete calculation scenario.
        
        Args:
            client_id: Client ID
            scenario: Scenario input parameters
            
        Returns:
            ScenarioOut with all calculated results
            
        Raises:
            ValueError: If validation fails
        """
        # Validate client
        client = self._get_client(client_id)
        
        # Get current employment
        employment = self._get_current_employment(client_id)
        
        # Get tax parameters
        params = self.tax_provider.get_params()
        
        # Determine end date for calculations
        end_date = scenario.planned_termination_date or date.today()
        
        # 1) Calculate seniority
        seniority = self.engines['seniority'].calculate(
            start_date=employment.start_date,
            end_date=end_date
        )
        
        # 2) Calculate grant (using base amount of 100,000 as example)
        base_amount = 100_000.0
        grant = self.engines['grant'].calculate(
            base_amount=base_amount,
            start_date=employment.start_date,
            end_date=end_date,
            params=params
        )
        
        # 3) Calculate pension from net grant
        pension_monthly = self.engines['pension'].calculate(
            capital=grant['net'],
            params=params
        )
        
        # 4) Generate cashflow (12 months as example)
        income = scenario.other_incomes_monthly or pension_monthly
        expense = scenario.monthly_expenses or 0.0
        cashflow = self.engines['cashflow'].calculate(
            start_date=end_date,
            months=12,
            income=income,
            expense=expense
        )
        
        # Return results
        return ScenarioOut(
            seniority_years=seniority,
            grant_gross=grant['gross'],
            grant_exempt=grant['exempt'],
            grant_tax=grant['tax'],
            grant_net=grant['net'],
            pension_monthly=pension_monthly,
            indexation_factor=grant['indexation_factor'],
            cashflow=cashflow,
        )
    
    def calculate_seniority_only(self, client_id: int, end_date: date = None) -> float:
        """
        Calculate only seniority for a client.
        
        Args:
            client_id: Client ID
            end_date: End date for calculation (defaults to today)
            
        Returns:
            Years of seniority
        """
        employment = self._get_current_employment(client_id)
        return self.engines['seniority'].calculate(
            start_date=employment.start_date,
            end_date=end_date
        )
    
    def calculate_grant_only(
        self,
        client_id: int,
        base_amount: float,
        end_date: date = None
    ) -> dict:
        """
        Calculate only grant for a client.
        
        Args:
            client_id: Client ID
            base_amount: Base grant amount
            end_date: End date for calculation (defaults to today)
            
        Returns:
            Dictionary with grant components
        """
        employment = self._get_current_employment(client_id)
        params = self.tax_provider.get_params()
        
        return self.engines['grant'].calculate(
            base_amount=base_amount,
            start_date=employment.start_date,
            end_date=end_date or date.today(),
            params=params
        )
