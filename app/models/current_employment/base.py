"""
Base utilities for employment models
"""
from datetime import datetime, timezone


def utcnow():
    """Return current UTC time with timezone awareness"""
    return datetime.now(timezone.utc)
