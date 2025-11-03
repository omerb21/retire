"""
Base Engine - Abstract Base Class
==================================

Defines the interface for all calculation engines.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.providers.tax_params import TaxParamsProvider


class BaseEngine(ABC):
    """
    Abstract base class for all calculation engines.
    
    Provides common initialization and interface definition.
    """
    
    def __init__(self, db: Session = None, tax_provider: TaxParamsProvider = None):
        """
        Initialize the base engine.
        
        Args:
            db: Database session (optional, not all engines need it)
            tax_provider: Tax parameters provider (optional, not all engines need it)
        """
        self.db = db
        self.tax_provider = tax_provider
    
    @abstractmethod
    def calculate(self, *args, **kwargs) -> Any:
        """
        Perform the calculation.
        
        This method must be implemented by all subclasses.
        
        Returns:
            Calculation result (type varies by engine)
        """
        pass
    
    def validate_inputs(self, **kwargs) -> bool:
        """
        Validate input parameters.
        
        Can be overridden by subclasses for specific validation.
        
        Returns:
            True if inputs are valid
            
        Raises:
            ValueError: If inputs are invalid
        """
        return True
