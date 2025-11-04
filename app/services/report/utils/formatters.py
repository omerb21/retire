"""
Data formatting utilities for reports.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional


class DataFormatters:
    """Utilities for formatting data in reports."""
    
    @staticmethod
    def format_currency(amount: float, currency: str = "₪") -> str:
        """
        Format number as currency with thousands separator.
        
        Args:
            amount: Amount to format
            currency: Currency symbol
            
        Returns:
            Formatted currency string
        """
        try:
            return f"{amount:,.0f} {currency}"
        except (ValueError, TypeError):
            return "N/A"
    
    @staticmethod
    def format_date(date: Optional[datetime], format_str: str = '%d/%m/%Y') -> str:
        """
        Format datetime object to string.
        
        Args:
            date: Datetime object
            format_str: Format string
            
        Returns:
            Formatted date string or 'N/A'
        """
        if date is None:
            return 'N/A'
        try:
            return date.strftime(format_str)
        except (AttributeError, ValueError):
            return 'N/A'
    
    @staticmethod
    def format_percentage(value: float, decimals: int = 1) -> str:
        """
        Format number as percentage.
        
        Args:
            value: Value to format (0-1 or 0-100)
            decimals: Number of decimal places
            
        Returns:
            Formatted percentage string
        """
        try:
            # Assume value is already in percentage form if > 1
            if value > 1:
                return f"{value:.{decimals}f}%"
            else:
                return f"{value * 100:.{decimals}f}%"
        except (ValueError, TypeError):
            return "N/A"
    
    @staticmethod
    def parse_json_safely(data: Any) -> Dict:
        """
        Safely parse JSON string or return dict.
        
        Args:
            data: JSON string or dict
            
        Returns:
            Parsed dictionary or empty dict on error
        """
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @staticmethod
    def format_phone(phone: Optional[str]) -> str:
        """
        Format phone number.
        
        Args:
            phone: Phone number string
            
        Returns:
            Formatted phone or 'N/A'
        """
        if not phone:
            return 'N/A'
        # Remove non-numeric characters
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return phone
    
    @staticmethod
    def format_address(street: Optional[str], city: Optional[str]) -> str:
        """
        Format address from components.
        
        Args:
            street: Street address
            city: City name
            
        Returns:
            Formatted address or 'N/A'
        """
        parts = [p for p in [street, city] if p]
        return ', '.join(parts) if parts else 'N/A'
    
    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        Safely convert value to float.
        
        Args:
            value: Value to convert
            default: Default value on error
            
        Returns:
            Float value or default
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        Safely convert value to int.
        
        Args:
            value: Value to convert
            default: Default value on error
            
        Returns:
            Int value or default
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
