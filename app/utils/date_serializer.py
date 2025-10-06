"""
Unified date serialization utilities for consistent API responses
"""
from datetime import date, datetime
from typing import Any, Union


def serialize_date_to_iso(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Convert any date-like object to ISO string format (YYYY-MM-DD)
    
    Args:
        date_obj: Date object, datetime object, or string
        
    Returns:
        ISO formatted date string (YYYY-MM-DD)
    """
    if date_obj is None:
        return ""
    
    if isinstance(date_obj, str):
        # Already a string, ensure it's in correct format
        if len(date_obj) >= 10:
            return date_obj[:10]  # Take first 10 chars (YYYY-MM-DD)
        return date_obj
    
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime("%Y-%m-%d")
    
    return str(date_obj)


def serialize_monthly_date(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Convert date to monthly format (YYYY-MM-01) for cashflow data
    
    Args:
        date_obj: Date object, datetime object, or string
        
    Returns:
        Monthly date string (YYYY-MM-01)
    """
    if date_obj is None:
        return ""
    
    if isinstance(date_obj, str):
        if len(date_obj) >= 7:
            year_month = date_obj[:7]  # YYYY-MM
            return f"{year_month}-01"
        return date_obj
    
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime("%Y-%m-01")
    
    return str(date_obj)


def extract_year_from_date(date_obj: Union[date, datetime, str, None]) -> str:
    """
    Extract year from any date-like object
    
    Args:
        date_obj: Date object, datetime object, or string
        
    Returns:
        Year as string (YYYY)
    """
    if date_obj is None:
        return ""
    
    if isinstance(date_obj, str):
        return date_obj[:4] if len(date_obj) >= 4 else date_obj
    
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime("%Y")
    
    return str(date_obj)[:4]


def normalize_cashflow_row(row: dict) -> dict:
    """
    Normalize a cashflow row to ensure consistent date format
    
    Args:
        row: Cashflow row dictionary
        
    Returns:
        Normalized row with date as ISO string
    """
    normalized = dict(row)
    if 'date' in normalized:
        normalized['date'] = serialize_monthly_date(normalized['date'])
    return normalized
