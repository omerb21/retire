"""
Enums and constants for tax calculations.
ENUMs וקבועים לחישובי מס.
"""

from typing import Dict


# קבועים בסיסיים
MONTHS_IN_YEAR = 12
DAYS_IN_YEAR = 365.25  # כולל שנים מעוברות

# סוגי הכנסות למטרות מס
INCOME_TYPES: Dict[str, str] = {
    'salary': 'שכר עבודה',
    'pension': 'פנסיה',
    'rental': 'הכנסה משכירות',
    'capital_gains': 'רווח הון',
    'business': 'הכנסה עצמאית',
    'interest': 'ריבית',
    'dividends': 'דיבידנדים',
    'other': 'הכנסות אחרות'
}

# סטטוסים משפחתיים
MARITAL_STATUS: Dict[str, str] = {
    'single': 'רווק/ה',
    'married': 'נשוי/ה',
    'divorced': 'גרוש/ה',
    'widowed': 'אלמן/ה'
}
