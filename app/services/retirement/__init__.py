"""
Retirement Scenarios Module
מודול לבניית תרחישי פרישה

This module provides functionality for building and analyzing retirement scenarios.

Structure:
- constants.py: קבועים
- scenario_builder.py: מנהל ראשי
- base_scenario_builder.py: מחלקת בסיס
- scenarios/: מימושי תרחישים
  - max_pension_scenario.py: תרחיש מקסימום קצבה
  - max_capital_scenario.py: תרחיש מקסימום הון
  - max_npv_scenario.py: תרחיש מאוזן
- services/: שירותים
  - state_service.py: ניהול מצב
  - conversion_service.py: המרות
  - termination_service.py: טיפול בעזיבת עבודה
  - portfolio_import_service.py: ייבוא תיק פנסיוני
- utils/: כלי עזר
  - pension_utils.py: פונקציות קצבה
  - capital_utils.py: פונקציות הון
  - calculation_utils.py: חישובים
  - serialization_utils.py: סריאליזציה
"""

from .constants import (
    PENSION_COEFFICIENT,
    MINIMUM_PENSION,
    HIGH_QUALITY_ANNUITY_THRESHOLD,
    DEFAULT_DISCOUNT_RATE,
    MAX_AGE_FOR_NPV
)

from .scenario_builder import RetirementScenariosBuilder

__all__ = [
    'RetirementScenariosBuilder',
    'PENSION_COEFFICIENT',
    'MINIMUM_PENSION',
    'HIGH_QUALITY_ANNUITY_THRESHOLD',
    'DEFAULT_DISCOUNT_RATE',
    'MAX_AGE_FOR_NPV'
]
