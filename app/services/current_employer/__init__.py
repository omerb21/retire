"""
Current Employer Service Package
חבילת שירותי מעסיק נוכחי

מודול מפוצל לשירותים נפרדים:
- EmploymentService: ניהול העסקה (יצירה, עדכון, קריאה)
- GrantService: ניהול מענקים
- TerminationService: עיבוד סיום העסקה
- ServiceYearsCalculator: חישוב שנות ותק
- SeveranceCalculator: חישוב פיצויים
- GrantCalculator: חישוב מענקים
"""

from .employment import EmploymentService
from .grants import GrantService
from .termination import TerminationService
from .calculations import (
    ServiceYearsCalculator,
    SeveranceCalculator,
    GrantCalculator
)

__all__ = [
    'EmploymentService',
    'GrantService',
    'TerminationService',
    'ServiceYearsCalculator',
    'SeveranceCalculator',
    'GrantCalculator'
]
