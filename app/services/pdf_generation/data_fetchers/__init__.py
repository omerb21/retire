"""
מודול שליפת נתונים מה-DB
"""

from .fixation_data import fetch_fixation_data, FixationData

__all__ = [
    'fetch_fixation_data',
    'FixationData',
]
