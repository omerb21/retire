"""
Base Scenario Builder

כלי בסיס לבניית תרחישי פרישה
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger("app.scenarios.base")


class BaseScenarioBuilder:
    """Base class for all retirement scenario builders"""
    
    def __init__(
        self,
        db: Session,
        client_id: int,
        retirement_age: int,
        pension_portfolio: Optional[List[Dict]] = None
    ):
        self.db = db
        self.client_id = client_id
        self.retirement_age = retirement_age
        self.pension_portfolio = pension_portfolio or []
        self.scenario_results = {}
    
    def build_scenario(self) -> Dict:
        """Build and return the scenario results
        
        This method must be implemented by all subclasses
        """
        raise NotImplementedError("Subclasses must implement build_scenario()")
    
    def _import_pension_portfolio_if_needed(self) -> None:
        """Import pension portfolio data if provided"""
        if not self.pension_portfolio:
            return
            
        logger.info("📥 Importing pension portfolio data...")
        # Implementation for importing pension portfolio
        # This is a placeholder - actual implementation will depend on your data model
        
    def _calculate_scenario_results(self, scenario_name: str) -> Dict:
        """Calculate and return the scenario results"""
        # Common calculations can be added here
        return {
            "scenario_name": scenario_name,
            "client_id": self.client_id,
            "retirement_age": self.retirement_age,
            # Add more common fields as needed
        }
        
    def _log_scenario_start(self, scenario_name: str) -> None:
        """Log the start of scenario processing"""
        logger.info(f"🚀 Starting scenario: {scenario_name}")
        logger.info(f"Client ID: {self.client_id}")
        logger.info(f"Retirement age: {self.retirement_age}")
        
    def _log_scenario_complete(self, scenario_name: str) -> None:
        """Log the completion of scenario processing"""
        logger.info(f"✅ Completed scenario: {scenario_name}")
        logger.info("-" * 50)
