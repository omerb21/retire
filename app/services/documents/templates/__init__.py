"""
מודול תבניות HTML למסמכים
"""

from .commutations_template import CommutationsHTMLTemplate
from .grants_template import GrantsHTMLTemplate
from .styles import get_base_styles
from .summary_template import SummaryHTMLTemplate

__all__ = [
    "get_base_styles",
    "GrantsHTMLTemplate",
    "CommutationsHTMLTemplate",
    "SummaryHTMLTemplate",
]
