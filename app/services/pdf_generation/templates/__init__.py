"""
מודול תבניות HTML ל-PDFs
"""

from .fixation_template import FixationHTMLTemplate
from .styles import get_fixation_styles

__all__ = [
    'FixationHTMLTemplate',
    'get_fixation_styles',
]
