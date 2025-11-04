"""
Income tax brackets for Israel.
מדרגות מס הכנסה לישראל.
"""

from typing import List
from .base_models import TaxBracket


# מדרגות מס הכנסה לשנת 2024 - מעודכן לנתונים הנכונים
INCOME_TAX_BRACKETS_2024: List[TaxBracket] = [
    TaxBracket(0, 84120, 0.10, "מדרגה ראשונה - 10%"),
    TaxBracket(84121, 120720, 0.14, "מדרגה שנייה - 14%"),
    TaxBracket(120721, 193800, 0.20, "מדרגה שלישית - 20%"),
    TaxBracket(193801, 269280, 0.31, "מדרגה רביעית - 31%"),
    TaxBracket(269281, 560280, 0.35, "מדרגה חמישית - 35%"),
    TaxBracket(560281, 721560, 0.47, "מדרגה שישית - 47%"),
    TaxBracket(721561, None, 0.50, "מדרגה עליונה - 50%")
]

# מדרגות מס הכנסה לשנת 2025 - מעודכן לנתונים הנכונים
INCOME_TAX_BRACKETS_2025: List[TaxBracket] = [
    TaxBracket(0, 84120, 0.10, "מדרגה ראשונה - 10%"),
    TaxBracket(84121, 120720, 0.14, "מדרגה שנייה - 14%"),
    TaxBracket(120721, 193800, 0.20, "מדרגה שלישית - 20%"),
    TaxBracket(193801, 269280, 0.31, "מדרגה רביעית - 31%"),
    TaxBracket(269281, 560280, 0.35, "מדרגה חמישית - 35%"),
    TaxBracket(560281, 721560, 0.47, "מדרגה שישית - 47%"),
    TaxBracket(721561, None, 0.50, "מדרגה עליונה - 50%")
]

# מדרגות מס הכנסה לשנת 2026 (זהה ל-2025 כברירת מחדל)
INCOME_TAX_BRACKETS_2026: List[TaxBracket] = [
    TaxBracket(0, 84120, 0.10, "מדרגה ראשונה - 10%"),
    TaxBracket(84121, 120720, 0.14, "מדרגה שנייה - 14%"),
    TaxBracket(120721, 193800, 0.20, "מדרגה שלישית - 20%"),
    TaxBracket(193801, 269280, 0.31, "מדרגה רביעית - 31%"),
    TaxBracket(269281, 560280, 0.35, "מדרגה חמישית - 35%"),
    TaxBracket(560281, 721560, 0.47, "מדרגה שישית - 47%"),
    TaxBracket(721561, None, 0.50, "מדרגה עליונה - 50%")
]


def get_tax_brackets(year: int = None) -> List[TaxBracket]:
    """
    מחזיר את מדרגות המס לשנה מסוימת.
    
    Args:
        year: שנת המס (ברירת מחדל: 2024)
        
    Returns:
        רשימת מדרגות המס לשנה המבוקשת
    """
    if year is None:
        year = 2024
        
    if year >= 2026:
        return INCOME_TAX_BRACKETS_2026
    elif year >= 2025:
        return INCOME_TAX_BRACKETS_2025
    else:
        return INCOME_TAX_BRACKETS_2024
