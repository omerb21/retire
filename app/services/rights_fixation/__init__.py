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

# ייבוא כל הפונקציות הציבוריות מהמודולים השונים
from .indexation import (
    calculate_adjusted_amount,
    index_grant
)

from .work_ratio import (
    work_ratio_within_last_32y,
    ratio_last_32y
)

from .exemption_caps import (
    get_monthly_cap,
    get_exemption_percentage,
    calc_exempt_capital,
    ANNUAL_CAPS,
    EXEMPTION_PERCENTAGES,
    MULTIPLIER
)

from .grant_impact import (
    compute_grant_effect,
    compute_client_exemption
)

from .eligibility import (
    calculate_eligibility_age
)

from .core import (
    process_grant,
    calculate_full_fixation
)

# רשימת כל הפונקציות והמשתנים הציבוריים
__all__ = [
    # Indexation
    'calculate_adjusted_amount',
    'index_grant',
    
    # Work Ratio
    'work_ratio_within_last_32y',
    'ratio_last_32y',
    
    # Exemption Caps
    'get_monthly_cap',
    'get_exemption_percentage',
    'calc_exempt_capital',
    'ANNUAL_CAPS',
    'EXEMPTION_PERCENTAGES',
    'MULTIPLIER',
    
    # Grant Impact
    'compute_grant_effect',
    'compute_client_exemption',
    
    # Eligibility
    'calculate_eligibility_age',
    
    # Core
    'process_grant',
    'calculate_full_fixation'
]
