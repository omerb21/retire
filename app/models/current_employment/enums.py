"""
Enums for employment models
"""
import enum


class ActiveContinuityType(enum.Enum):
    """Enum for active continuity types"""
    none = "none"
    severance = "severance"
    pension = "pension"


class GrantType(enum.Enum):
    """Enum for grant types"""
    severance = "severance"
    adjustment = "adjustment"
    other = "other"
