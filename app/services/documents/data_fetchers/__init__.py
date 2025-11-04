"""
מודול שליפת נתונים מה-DB למסמכים
"""

from .fixation_data import fetch_fixation_data, FixationData
from .client_data import fetch_client_data
from .grants_data import fetch_grants_data
from .pension_data import fetch_pension_data
from .commutations_data import fetch_commutations_data

__all__ = [
    'fetch_fixation_data',
    'FixationData',
    'fetch_client_data',
    'fetch_grants_data',
    'fetch_pension_data',
    'fetch_commutations_data',
]
