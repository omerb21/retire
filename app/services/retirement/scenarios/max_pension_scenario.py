"""
Maximum Pension Scenario
תרחיש מקסימום קצבה
"""
import logging
from typing import Dict
from ..base_scenario_builder import BaseScenarioBuilder

logger = logging.getLogger("app.scenarios.max_pension")


class MaxPensionScenario(BaseScenarioBuilder):
    """תרחיש 1: מקסימום קצבה"""
    
    def build_scenario(self) -> Dict:
        """בניית תרחיש מקסימום קצבה"""
        logger.info("📊 Building Scenario 1: Maximum Pension")
        
        # 0. Import pension portfolio if provided
        self._import_pension_portfolio_if_needed()
        
        # 1. Convert all pension funds to pensions
        self.conversion_service.convert_all_pension_funds_to_pension()
        
        # 1.5. Convert education funds to exempt pensions
        self.conversion_service.convert_education_funds_to_pension()
        
        # 2. Convert taxable capital assets to pensions
        self.conversion_service.convert_taxable_capital_to_pension()
        
        # 3. Convert tax-exempt capital to exempt pension (NOT income!)
        self.conversion_service.convert_exempt_capital_to_pension()
        
        # 4. Handle termination event
        self.termination_service.handle_termination_for_pension()
        
        # 5. Verify fixation and exempt pension
        self.conversion_service.verify_fixation_and_exempt_pension()
        
        # 6. Calculate NPV and return results
        return self._calculate_scenario_results("מקסימום קצבה")
