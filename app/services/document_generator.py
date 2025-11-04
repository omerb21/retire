"""
מודול ליצירת מסמכי קיבוע זכויות - Backward Compatibility Wrapper

הקובץ המקורי פוצל למבנה מודולרי תחת app/services/documents/
קובץ זה נשמר לצורך תאימות לאחור עם קוד קיים.

מבנה חדש:
- documents/utils/ - פונקציות עזר וניהול נתיבים
- documents/converters/ - המרת HTML ל-PDF
- documents/templates/ - תבניות HTML למסמכים
- documents/data_fetchers/ - שליפת נתונים מ-DB
- documents/generators/ - יצירת מסמכים ספציפיים

לשימוש חדש, ייבא ישירות מהמודול החדש:
    from app.services.documents import generate_document_package
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional

# ייבוא מהמודול המודולרי החדש
from app.services.documents import (
    generate_document_package,
    fill_161d_form,
    generate_grants_appendix,
    generate_commutations_appendix,
    generate_actual_commutations_appendix,
    generate_summary_table
)
from app.services.documents.utils import (
    get_client_package_dir,
    TEMPLATE_DIR,
    TEMPLATE_161D,
    PACKAGES_DIR
)
from app.services.documents.converters import html_to_pdf

# ייצוא לצורך backward compatibility
__all__ = [
    'generate_document_package',
    'fill_161d_form',
    'generate_grants_appendix',
    'generate_commutations_appendix',
    'generate_actual_commutations_appendix',
    'generate_summary_table',
    'get_client_package_dir',
    'html_to_pdf',
    'TEMPLATE_DIR',
    'TEMPLATE_161D',
    'PACKAGES_DIR',
]


# הפונקציות הישנות זמינות דרך הייבוא לעיל
# כל הקוד הקיים ממשיך לעבוד ללא שינוי!
