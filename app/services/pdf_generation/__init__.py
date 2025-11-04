"""
מודול יצירת PDFs - מבנה מודולרי

מבנה:
- converters: המרת HTML ל-PDF
- templates: תבניות HTML
- data_fetchers: שליפת נתונים מה-DB
- generators: יצירת PDFs
"""

from .generators.fixation_generator import generate_fixation_summary_pdf

__all__ = [
    'generate_fixation_summary_pdf',
]
