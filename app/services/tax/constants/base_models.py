"""
Base models for tax calculations.
מודלים בסיסיים לחישובי מס.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TaxBracket:
    """
    מדרגת מס.
    
    Attributes:
        min_income: הכנסה מינימלית למדרגה
        max_income: הכנסה מקסימלית למדרגה (None = אין תקרה)
        rate: שיעור המס (0.1 = 10%)
        description: תיאור המדרגה
    """
    min_income: float
    max_income: Optional[float]  # None = אין תקרה
    rate: float  # שיעור המס (0.1 = 10%)
    description: str


@dataclass
class TaxCredit:
    """
    נקודת זיכוי במס.
    
    Attributes:
        code: קוד הזיכוי
        name: שם הזיכוי
        amount: סכום הזיכוי בש"ח
        description: תיאור הזיכוי
        conditions: תנאי הזכאות (אופציונלי)
    """
    code: str
    name: str
    amount: float  # סכום הזיכוי בש"ח
    description: str
    conditions: str = ""
