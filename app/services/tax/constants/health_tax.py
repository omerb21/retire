"""
Health tax rates for Israel.
שיעורי מס בריאות לישראל.
"""

from typing import Dict


# מס בריאות 2024
HEALTH_TAX_2024: Dict[str, float] = {
    'rate_low': 0.031,  # 3.1% עד התקרה הנמוכה
    'rate_high': 0.050,  # 5.0% מעל התקרה הנמוכה
    'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
    'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
    'max_monthly_payment': 2245,  # תשלום מקסימלי חודשי
}

# מס בריאות 2025 (זהה ל-2024 כברירת מחדל)
HEALTH_TAX_2025: Dict[str, float] = {
    'rate_low': 0.031,  # 3.1% עד התקרה הנמוכה
    'rate_high': 0.050,  # 5.0% מעל התקרה הנמוכה
    'low_threshold_monthly': 6331,  # תקרה נמוכה חודשית
    'high_threshold_monthly': 47310,  # תקרה עליונה חודשית
    'max_monthly_payment': 2245,  # תשלום מקסימלי חודשי
}


def get_health_tax_rates(year: int = None) -> Dict[str, float]:
    """
    מחזיר את שיעורי מס הבריאות לשנה מסוימת.
    
    Args:
        year: שנת המס (ברירת מחדל: 2024)
        
    Returns:
        מילון עם שיעורי מס הבריאות
    """
    if year is None or year < 2025:
        return HEALTH_TAX_2024
    else:
        return HEALTH_TAX_2025
