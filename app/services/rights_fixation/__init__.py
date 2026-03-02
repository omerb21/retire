"""
מודול קיבוע זכויות - מימוש מלא על בסיס המערכת הקיימת
מבוסס על הלוגיקה מתוך תיקיית "מערכת קיבוע זכויות"

מודול זה מפוצל למספר תת-מודולים לשיפור הארגון והתחזוקה:
- indexation: חישובי הצמדה למדד
- work_ratio: חישוב יחס עבודה ב-32 השנים האחרונות
- exemption_caps: תקרות והון פטור
- grant_impact: חישוב פגיעה בהון הפטור
- eligibility: חישוב זכאות גיל
- core: פונקציות שירות מרכזיות
"""

from .core import calculate_full_fixation, process_grant
from .eligibility import calculate_eligibility_age
from .exemption_caps import (
    ANNUAL_CAPS,
    EXEMPTION_PERCENTAGES,
    MULTIPLIER,
    calc_exempt_capital,
    get_exemption_percentage,
    get_monthly_cap,
)
from .grant_impact import compute_client_exemption, compute_grant_effect
from .idf_fixation import IdfFixationResult, compute_idf_fixation_impact

# ייבוא כל הפונקציות הציבוריות מהמודולים השונים
from .indexation import calculate_adjusted_amount, index_grant
from .work_ratio import ratio_last_32y, work_ratio_within_last_32y

# רשימת כל הפונקציות והמשתנים הציבוריים
__all__ = [
    # Indexation
    "calculate_adjusted_amount",
    "index_grant",
    # Work Ratio
    "work_ratio_within_last_32y",
    "ratio_last_32y",
    # Exemption Caps
    "get_monthly_cap",
    "get_exemption_percentage",
    "calc_exempt_capital",
    "ANNUAL_CAPS",
    "EXEMPTION_PERCENTAGES",
    "MULTIPLIER",
    # Grant Impact
    "compute_grant_effect",
    "compute_client_exemption",
    # IDF Security Forces fixation helpers
    "IdfFixationResult",
    "compute_idf_fixation_impact",
    # Eligibility
    "calculate_eligibility_age",
    # Core
    "process_grant",
    "calculate_full_fixation",
]
