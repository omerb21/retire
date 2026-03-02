"""
מודול המרת HTML ל-PDF
"""

from .html_to_pdf import find_wkhtmltopdf, html_to_pdf

__all__ = [
    "html_to_pdf",
    "find_wkhtmltopdf",
]
