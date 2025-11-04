"""
Tax credits for Israel.
נקודות זיכוי במס לישראל.
"""

from typing import List, Dict
from .base_models import TaxCredit


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

# נקודות זיכוי במס לשנת 2025 (זהה ל-2024 כברירת מחדל)
TAX_CREDITS_2025: List[TaxCredit] = [
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

# ערך נקודת זיכוי (NIS)
TAX_CREDIT_POINT_VALUE: Dict[int, float] = {
    2024: 2640,  # ערך נקודת זיכוי לשנת 2024
    2025: 2904,  # ערך נקודת זיכוי לשנת 2025
}


def get_tax_credits(year: int = None) -> List[TaxCredit]:
    """
    מחזיר את נקודות הזיכוי לשנה מסוימת.
    
    Args:
        year: שנת המס (ברירת מחדל: 2024)
        
    Returns:
        רשימת נקודות הזיכוי במס
    """
    if year is None or year < 2025:
        return TAX_CREDITS_2024
    else:
        return TAX_CREDITS_2025
