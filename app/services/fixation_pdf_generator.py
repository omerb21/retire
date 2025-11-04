"""
יצירת PDFs של קיבוע זכויות - Backward Compatibility Wrapper

הקובץ המקורי פוצל למבנה מודולרי תחת app/services/pdf_generation/
קובץ זה נשמר לצורך תאימות לאחור עם קוד קיים.

מבנה חדש:
- pdf_generation/converters/ - המרת HTML ל-PDF
- pdf_generation/templates/ - תבניות HTML
- pdf_generation/data_fetchers/ - שליפת נתונים מ-DB
- pdf_generation/generators/ - יצירת PDFs

לשימוש חדש, ייבא ישירות מהמודול החדש:
    from app.services.pdf_generation import generate_fixation_summary_pdf
"""
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional

# ייבוא מהמודול המודולרי החדש
from app.services.pdf_generation import generate_fixation_summary_pdf
from app.services.pdf_generation.converters import html_to_pdf

# ייצוא לצורך backward compatibility
__all__ = [
    'generate_fixation_summary_pdf',
    'html_to_pdf',
]
