"""
Tax constants package - קבועי מס.
מודול זה מכיל את כל הקבועים הקשורים למיסוי בישראל.
"""

from .base_models import TaxBracket, TaxCredit
from .income_tax import INCOME_TAX_BRACKETS_2024, INCOME_TAX_BRACKETS_2025, get_tax_brackets
from .national_insurance import NATIONAL_INSURANCE_2024, get_national_insurance_rates
from .health_tax import HEALTH_TAX_2024, get_health_tax_rates
from .tax_credits import TAX_CREDITS_2024, TAX_CREDIT_POINT_VALUE, get_tax_credits
from .pension_tax import PENSION_TAX_EXEMPTIONS, get_pension_exemptions
from .special_rates import SPECIAL_TAX_RATES, INDEXATION_RATES
from .enums import INCOME_TYPES, MARITAL_STATUS, MONTHS_IN_YEAR, DAYS_IN_YEAR

# Backward compatibility - מחלקה מרכזית לגישה לכל הקבועים
class TaxConstants:
    """
    קבועי מס עדכניים לישראל.
    מחלקה זו מספקת גישה מרכזית לכל קבועי המס.
    """
    
    # שנת המס הנוכחית
    CURRENT_TAX_YEAR = 2024
    
    # מדרגות מס הכנסה
    INCOME_TAX_BRACKETS_2024 = INCOME_TAX_BRACKETS_2024
    INCOME_TAX_BRACKETS_2025 = INCOME_TAX_BRACKETS_2025
    
    # ביטוח לאומי
    NATIONAL_INSURANCE_2024 = NATIONAL_INSURANCE_2024
    
    # מס בריאות
    HEALTH_TAX_2024 = HEALTH_TAX_2024
    
    # נקודות זיכוי במס
    TAX_CREDITS_2024 = TAX_CREDITS_2024
    TAX_CREDIT_POINT_VALUE = TAX_CREDIT_POINT_VALUE
    
    # פטורים ממס לפנסיונרים
    PENSION_TAX_EXEMPTIONS = PENSION_TAX_EXEMPTIONS
    
    # שיעורי מס מיוחדים
    SPECIAL_TAX_RATES = SPECIAL_TAX_RATES
    INDEXATION_RATES = INDEXATION_RATES
    
    @classmethod
    def get_tax_brackets(cls, year: int = None):
        """מחזיר את מדרגות המס לשנה מסוימת"""
        return get_tax_brackets(year)
    
    @classmethod
    def get_national_insurance_rates(cls, year: int = None):
        """מחזיר את שיעורי הביטוח הלאומי לשנה מסוימת"""
        return get_national_insurance_rates(year)
    
    @classmethod
    def get_health_tax_rates(cls, year: int = None):
        """מחזיר את שיעורי מס הבריאות לשנה מסוימת"""
        return get_health_tax_rates(year)
    
    @classmethod
    def get_tax_credits(cls, year: int = None):
        """מחזיר את נקודות הזיכוי לשנה מסוימת"""
        return get_tax_credits(year)
    
    @classmethod
    def get_pension_exemptions(cls):
        """מחזיר את הפטורים ממס לפנסיונרים"""
        return get_pension_exemptions()


__all__ = [
    'TaxBracket',
    'TaxCredit',
    'TaxConstants',
    'INCOME_TAX_BRACKETS_2024',
    'INCOME_TAX_BRACKETS_2025',
    'NATIONAL_INSURANCE_2024',
    'HEALTH_TAX_2024',
    'TAX_CREDITS_2024',
    'TAX_CREDIT_POINT_VALUE',
    'PENSION_TAX_EXEMPTIONS',
    'SPECIAL_TAX_RATES',
    'INDEXATION_RATES',
    'INCOME_TYPES',
    'MARITAL_STATUS',
    'MONTHS_IN_YEAR',
    'DAYS_IN_YEAR',
]
