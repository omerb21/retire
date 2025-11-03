"""
Engine Factory - Factory Pattern for Engine Creation
=====================================================

Provides factory methods for creating calculation engine instances.
"""

from typing import Dict
from sqlalchemy.orm import Session
from app.providers.tax_params import TaxParamsProvider
from .engine.seniority_engine import SeniorityEngine
from .engine.grant_engine import GrantEngine
from .engine.pension_engine import PensionEngine
from .engine.cashflow_engine import CashflowEngine


class EngineFactory:
    """
    Factory for creating calculation engine instances.
    
    Provides centralized creation of all engine types with proper
    dependency injection.
    """
    
    @staticmethod
    def create_engines(
        db: Session = None,
        tax_provider: TaxParamsProvider = None
    ) -> Dict[str, object]:
        """
        Create all calculation engines.
        
        Args:
            db: Database session (optional, only needed for certain engines)
            tax_provider: Tax parameters provider (optional, only needed for certain engines)
            
        Returns:
            Dictionary of engine instances keyed by engine type:
                - 'seniority': SeniorityEngine
                - 'grant': GrantEngine
                - 'pension': PensionEngine
                - 'cashflow': CashflowEngine
        """
        return {
            'seniority': SeniorityEngine(),
            'grant': GrantEngine(tax_provider) if tax_provider else None,
            'pension': PensionEngine(tax_provider),
            'cashflow': CashflowEngine()
        }
    
    @staticmethod
    def create_seniority_engine() -> SeniorityEngine:
        """
        Create a standalone seniority engine.
        
        Returns:
            SeniorityEngine instance
        """
        return SeniorityEngine()
    
    @staticmethod
    def create_grant_engine(tax_provider: TaxParamsProvider) -> GrantEngine:
        """
        Create a standalone grant engine.
        
        Args:
            tax_provider: Tax parameters provider
            
        Returns:
            GrantEngine instance
        """
        return GrantEngine(tax_provider)
    
    @staticmethod
    def create_pension_engine(tax_provider: TaxParamsProvider = None) -> PensionEngine:
        """
        Create a standalone pension engine.
        
        Args:
            tax_provider: Tax parameters provider (optional)
            
        Returns:
            PensionEngine instance
        """
        return PensionEngine(tax_provider)
    
    @staticmethod
    def create_cashflow_engine() -> CashflowEngine:
        """
        Create a standalone cashflow engine.
        
        Returns:
            CashflowEngine instance
        """
        return CashflowEngine()
