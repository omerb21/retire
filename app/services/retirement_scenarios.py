"""
Retirement Scenarios Builder Service - BACKWARD COMPATIBILITY WRAPPER
מייצר 3 תרחישי פרישה: מקסימום קצבה, מקסימום הון, מקסימום NPV

⚠️ DEPRECATED: This file is kept for backward compatibility only.
   New code should use: from app.services.retirement import RetirementScenariosBuilder

The actual implementation has been refactored into a modular structure:
- app/services/retirement/scenario_builder.py (main orchestrator)
- app/services/retirement/scenarios/ (scenario implementations)
- app/services/retirement/services/ (state, conversion, termination services)
- app/services/retirement/utils/ (utility functions)

All 1429 lines of the original code have been split into:
- 1 main orchestrator (scenario_builder.py)
- 1 base class (base_scenario_builder.py)
- 3 scenario implementations (max_pension, max_capital, max_npv)
- 4 service classes (state, conversion, termination, portfolio_import)
- 4 utility modules (pension_utils, capital_utils, calculation_utils, serialization_utils)
- 1 constants file

This provides better:
- Maintainability: Each file has a single responsibility
- Testability: Each component can be tested independently
- Reusability: Utility functions can be used across scenarios
- Readability: Smaller, focused files are easier to understand
"""
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

# Import from the new modular structure
from app.services.retirement import (
    RetirementScenariosBuilder as _NewRetirementScenariosBuilder,
    PENSION_COEFFICIENT,
    MINIMUM_PENSION,
    HIGH_QUALITY_ANNUITY_THRESHOLD
)

logger = logging.getLogger("app.scenarios")

# Re-export constants for backward compatibility
__all__ = [
    'RetirementScenariosBuilder',
    'PENSION_COEFFICIENT',
    'MINIMUM_PENSION',
    'HIGH_QUALITY_ANNUITY_THRESHOLD'
]


class RetirementScenariosBuilder(_NewRetirementScenariosBuilder):
    """
    בונה תרחישי פרישה - Backward Compatibility Wrapper
    
    This class simply inherits from the new modular implementation.
    All functionality has been moved to app/services/retirement/
    
    Usage (unchanged):
        builder = RetirementScenariosBuilder(db, client_id, retirement_age, pension_portfolio)
        scenarios = builder.build_all_scenarios()
    """
    pass
