"""
מודול יצירת מסמכי קיבוע זכויות - מבנה מודולרי

מבנה:
- utils: פונקציות עזר (ניהול תיקיות, קבועים)
- converters: המרת HTML ל-PDF
- templates: תבניות HTML למסמכים
- data_fetchers: שליפת נתונים מה-DB
- generators: יצירת מסמכים ספציפיים
"""

from .generators.package_generator import generate_document_package
from .generators.form_161d_generator import fill_161d_form
from .generators.grants_generator import generate_grants_appendix
from .generators.commutations_generator import (
    generate_commutations_appendix,
    generate_actual_commutations_appendix
)
from .generators.summary_generator import generate_summary_table

__all__ = [
    'generate_document_package',
    'fill_161d_form',
    'generate_grants_appendix',
    'generate_commutations_appendix',
    'generate_actual_commutations_appendix',
    'generate_summary_table',
]
