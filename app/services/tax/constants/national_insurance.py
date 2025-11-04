"""
National insurance rates for Israel.
שיעורי ביטוח לאומי לישראל.
"""

from typing import Dict


# ביטוח לאומי 2024
NATIONAL_INSURANCE_2024: Dict[str, float] = {
    'employee_rate_low': 0.004,  # 0.4% עד התקרה הנמוכה
    'employee_rate_high': 0.076,  # 7.6% מעל התקרה הנמוכה
    'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
    'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
    'max_monthly_payment': 3196,  # תשלום מקסימלי חודשי
}

# ביטוח לאומי 2025 (זהה ל-2024 כברירת מחדל)
NATIONAL_INSURANCE_2025: Dict[str, float] = {
    'employee_rate_low': 0.004,  # 0.4% עד התקרה הנמוכה
    'employee_rate_high': 0.076,  # 7.6% מעל התקרה הנמוכה
    'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
    'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
    'max_monthly_payment': 3196,  # תשלום מקסימלי חודשי
}


def get_national_insurance_rates(year: int = None) -> Dict[str, float]:
    """
    מחזיר את שיעורי הביטוח הלאומי לשנה מסוימת.
    
    Args:
        year: שנת המס (ברירת מחדל: 2024)
        
    Returns:
        מילון עם שיעורי הביטוח הלאומי
    """
    if year is None or year < 2025:
        return NATIONAL_INSURANCE_2024
    else:
        return NATIONAL_INSURANCE_2025
