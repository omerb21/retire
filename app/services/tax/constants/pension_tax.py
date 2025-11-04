"""
Pension tax exemptions for Israel.
פטורים ממס לפנסיונרים בישראל.
"""

from typing import Dict


# פטורים ממס לפנסיונרים
PENSION_TAX_EXEMPTIONS: Dict[str, float] = {
    'basic_exemption_monthly': 1000,  # פטור בסיסי חודשי לפנסיונר
    'veteran_exemption_monthly': 1500,  # פטור נוסף לוחם משוחרר
    'disability_exemption_monthly': 2000,  # פטור לנכה
    'age_threshold': 67,  # גיל זכאות לפטור
}


def get_pension_exemptions() -> Dict[str, float]:
    """
    מחזיר את הפטורים ממס לפנסיונרים.
    
    Returns:
        מילון עם פטורי המס לפנסיונרים
    """
    return PENSION_TAX_EXEMPTIONS
