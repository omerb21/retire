"""
קבועי מס הכנסה, ביטוח לאומי ומס בריאות לישראל
מעודכן לשנת המס 2024-2025
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import date

@dataclass
class TaxBracket:
    """מדרגת מס"""
    min_income: float
    max_income: float | None  # None = אין תקרה
    rate: float  # שיעור המס (0.1 = 10%)
    description: str

@dataclass
class TaxCredit:
    """נקודת זיכוי במס"""
    code: str
    name: str
    amount: float  # סכום הזיכוי בש"ח
    description: str
    conditions: str = ""

class TaxConstants:
    """קבועי מס עדכניים לישראל"""
    
    # שנת המס הנוכחית
    CURRENT_TAX_YEAR = 2024
    
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
    
    # ביטוח לאומי 2024
    NATIONAL_INSURANCE_2024 = {
        'employee_rate_low': 0.004,  # 0.4% עד התקרה הנמוכה
        'employee_rate_high': 0.076,  # 7.6% מעל התקרה הנמוכה
        'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
        'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
        'max_monthly_payment': 3196,  # תשלום מקסימלי חודשי
    }
    
    # מס בריאות 2024
    HEALTH_TAX_2024 = {
        'rate_low': 0.031,  # 3.1% עד התקרה הנמוכה
        'rate_high': 0.050,  # 5.0% מעל התקרה הנמוכה
        'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
        'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
        'max_monthly_payment': 2245,  # תשלום מקסימלי חודשי
    }
    
    # נקודות זיכוי במס לשנת 2024
    TAX_CREDITS_2024: List[TaxCredit] = [
        TaxCredit("basic", "נקודת זיכוי בסיסית", 2640, "זיכוי בסיסי לכל תושב ישראל"),
        TaxCredit("spouse", "בן/בת זוג", 2640, "זיכוי עבור בן/בת זוג שאינו עובד"),
        TaxCredit("child", "ילד", 1320, "זיכוי עבור כל ילד עד גיל 18"),
        TaxCredit("elderly", "זקנה", 2640, "זיכוי נוסף לגיל פרישה"),
        TaxCredit("new_immigrant", "עולה חדש", 3960, "זיכוי לעולה חדש בשנות הקליטה הראשונות"),
        TaxCredit("disabled", "נכה", 7920, "זיכוי לנכה לפי דרגת נכות"),
        TaxCredit("veteran", "נכה צה\"ל", 10560, "זיכוי לנכה צה\"ל"),
        TaxCredit("single_parent", "הורה יחיד", 2640, "זיכוי להורה יחיד"),
        TaxCredit("student", "סטודנט", 1980, "זיכוי לסטודנט במוסד מוכר"),
        TaxCredit("reserve_duty", "מילואים", 1320, "זיכוי עבור שירות מילואים"),
    ]
    
    # פטורים ממס לפנסיונרים
    PENSION_TAX_EXEMPTIONS = {
        'basic_exemption_monthly': 1000,  # פטור בסיסי חודשי לפנסיונר
        'veteran_exemption_monthly': 1500,  # פטור נוסף לוחם משוחרר
        'disability_exemption_monthly': 2000,  # פטור לנכה
        'age_threshold': 67,  # גיל זכאות לפטור
    }
    
    # שיעורי הצמדה למדד
    INDEXATION_RATES = {
        'cpi_annual': 0.025,  # 2.5% הצמדה שנתית למדד המחירים
        'salary_annual': 0.030,  # 3.0% הצמדה שנתית לשכר הממוצע
    }
    
    # ערך נקודת זיכוי (NIS)
    TAX_CREDIT_POINT_VALUE = {
        2024: 2640,  # ערך נקודת זיכוי לשנת 2024
        2025: 2904,  # ערך נקודת זיכוי לשנת 2025
    }
    
    # שיעורי מס מיוחדים לסוגי הכנסות שונות
    SPECIAL_TAX_RATES = {
        'rental_income': 0.10,  # מס קבוע 10% על הכנסה משכירות
        'capital_gains': 0.25,  # מס רווח הון 25%
        'dividend_income': 0.25,  # מס דיבידנד 25%
        'interest_income': 0.15,  # מס על ריבית 15%
    }
    
    @classmethod
    def get_tax_brackets(cls, year: int = None) -> List[TaxBracket]:
        """מחזיר את מדרגות המס לשנה מסוימת"""
        if year is None:
            year = cls.CURRENT_TAX_YEAR
            
        if year == 2026:
            # Use 2025 brackets for 2026 as a default, but adjust rates if needed
            return [
                TaxBracket(0, 84120, 0.10, "מדרגה ראשונה - 10%"),
                TaxBracket(84121, 120720, 0.14, "מדרגה שנייה - 14%"),
                TaxBracket(120721, 193800, 0.20, "מדרגה שלישית - 20%"),
                TaxBracket(193801, 269280, 0.31, "מדרגה רביעית - 31%"),
                TaxBracket(269281, 560280, 0.35, "מדרגה חמישית - 35%"),
                TaxBracket(560281, 721560, 0.47, "מדרגה שישית - 47%"),
                TaxBracket(721561, None, 0.50, "מדרגה עליונה - 50%")
            ]
        elif year >= 2025:
            return cls.INCOME_TAX_BRACKETS_2025
        else:
            return cls.INCOME_TAX_BRACKETS_2024
    
    @classmethod
    def get_national_insurance_rates(cls, year: int = None) -> Dict:
        """מחזיר את שיעורי הביטוח הלאומי לשנה מסוימת"""
        # כרגע יש לנו נתונים רק ל-2024
        return cls.NATIONAL_INSURANCE_2024
    
    @classmethod
    def get_health_tax_rates(cls, year: int = None) -> Dict:
        """מחזיר את שיעורי מס הבריאות לשנה מסוימת"""
        # כרגע יש לנו נתונים רק ל-2024
        return cls.HEALTH_TAX_2024
    
    @classmethod
    def get_tax_credits(cls, year: int = None) -> List[TaxCredit]:
        """מחזיר את נקודות הזיכוי לשנה מסוימת"""
        # כרגע יש לנו נתונים רק ל-2024
        return cls.TAX_CREDITS_2024
    
    @classmethod
    def get_pension_exemptions(cls) -> Dict:
        """מחזיר את הפטורים ממס לפנסיונרים"""
        return cls.PENSION_TAX_EXEMPTIONS

# קבועים נוספים
MONTHS_IN_YEAR = 12
DAYS_IN_YEAR = 365.25  # כולל שנים מעוברות

# סוגי הכנסות למטרות מס
INCOME_TYPES = {
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
MARITAL_STATUS = {
    'single': 'רווק/ה',
    'married': 'נשוי/ה',
    'divorced': 'גרוש/ה',
    'widowed': 'אלמן/ה'
}
