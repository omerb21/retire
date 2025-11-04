"""
מודול תבניות HTML למסמכים
"""

from .styles import get_base_styles
from .grants_template import GrantsHTMLTemplate
from .commutations_template import CommutationsHTMLTemplate
from .summary_template import SummaryHTMLTemplate

__all__ = [
    'get_base_styles',
    'GrantsHTMLTemplate',
    'CommutationsHTMLTemplate',
    'SummaryHTMLTemplate',
]
