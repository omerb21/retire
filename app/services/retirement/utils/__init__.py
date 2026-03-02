"""
Utility functions for retirement scenarios
פונקציות עזר לתרחישי פרישה
"""

from .calculation_utils import calculate_npv_dcf, calculate_years_to_age
from .capital_utils import (
    capitalize_pension_with_factor,
    create_capital_asset_from_pension,
)
from .pension_utils import (
    convert_balance_to_pension,
    convert_capital_to_pension,
    convert_education_fund_to_capital,
    convert_education_fund_to_pension,
)
from .serialization_utils import (
    serialize_additional_income,
    serialize_capital_asset,
    serialize_pension_fund,
    serialize_termination_event,
)

__all__ = [
    # Pension utilities
    "convert_balance_to_pension",
    "convert_capital_to_pension",
    "convert_education_fund_to_pension",
    "convert_education_fund_to_capital",
    # Capital utilities
    "create_capital_asset_from_pension",
    "capitalize_pension_with_factor",
    # Calculation utilities
    "calculate_npv_dcf",
    "calculate_years_to_age",
    # Serialization utilities
    "serialize_pension_fund",
    "serialize_capital_asset",
    "serialize_additional_income",
    "serialize_termination_event",
]
