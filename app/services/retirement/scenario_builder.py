"""
Main scenario builder orchestrator
מנהל ראשי לבניית תרחישים
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from .scenarios.max_pension_scenario import MaxPensionScenario
from .scenarios.max_capital_scenario import MaxCapitalScenario
from .scenarios.max_npv_scenario import MaxNPVScenario
from .services.state_service import StateService

logger = logging.getLogger("app.scenarios")


class RetirementScenariosBuilder:
    """בונה תרחישי פרישה - מחלקה ראשית"""
    
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
        
        # State service for saving/restoring state
        self.state_service = StateService(db, client_id)
    
    def build_all_scenarios(self) -> Dict[str, any]:
        """בונה את כל 3 התרחישים"""
        logger.info(f"🎯 Building scenarios for client {self.client_id}, retirement age {self.retirement_age}")
        
        # Save current state
        original_state = self.state_service.save_current_state()
        
        try:
            # Scenario 1: Maximum Pension
            logger.info("\n" + "="*60)
            scenario1_builder = MaxPensionScenario(
                self.db,
                self.client_id,
                self.retirement_age,
                self.pension_portfolio
            )
            scenario1 = scenario1_builder.build_scenario()
            
            # Restore state
            self.state_service.restore_state(original_state)
            
            # Scenario 2: Maximum Capital
            logger.info("\n" + "="*60)
            scenario2_builder = MaxCapitalScenario(
                self.db,
                self.client_id,
                self.retirement_age,
                self.pension_portfolio
            )
            scenario2 = scenario2_builder.build_scenario()
            
            # Restore state
            self.state_service.restore_state(original_state)
            
            # Scenario 3: Maximum NPV
            logger.info("\n" + "="*60)
            scenario3_builder = MaxNPVScenario(
                self.db,
                self.client_id,
                self.retirement_age,
                self.pension_portfolio
            )
            scenario3 = scenario3_builder.build_scenario()
            
            # Restore original state
            self.state_service.restore_state(original_state)
            
            logger.info("\n" + "="*60)
            logger.info("✅ All scenarios built successfully")
            
            return {
                "scenario_1_max_pension": scenario1,
                "scenario_2_max_capital": scenario2,
                "scenario_3_max_npv": scenario3
            }
            
        except Exception as e:
            logger.error(f"❌ Error building scenarios: {e}", exc_info=True)
            # Restore state on error
            self.state_service.restore_state(original_state)
            raise
    
    def _build_max_pension_scenario(self) -> Dict:
        """בניית תרחיש מקסימום קצבה - wrapper for backward compatibility"""
        scenario_builder = MaxPensionScenario(
            self.db,
            self.client_id,
            self.retirement_age,
            self.pension_portfolio
        )
        return scenario_builder.build_scenario()
    
    def _build_max_capital_scenario(self) -> Dict:
        """בניית תרחיש מקסימום הון - wrapper for backward compatibility"""
        scenario_builder = MaxCapitalScenario(
            self.db,
            self.client_id,
            self.retirement_age,
            self.pension_portfolio
        )
        return scenario_builder.build_scenario()
    
    def _build_max_npv_scenario(self) -> Dict:
        """בניית תרחיש מאוזן - wrapper for backward compatibility"""
        scenario_builder = MaxNPVScenario(
            self.db,
            self.client_id,
            self.retirement_age,
            self.pension_portfolio
        )
        return scenario_builder.build_scenario()
