"""
מודול שליפת נתונים מה-DB
"""

from .fixation_data import FixationData, fetch_fixation_data

__all__ = [
    "fetch_fixation_data",
    "FixationData",
]
