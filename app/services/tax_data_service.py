"""
Tax Data Service - Backward compatibility wrapper
This file maintains backward compatibility by re-exporting from the new modular structure.

For new code, import directly from app.services.tax_data
"""

# Import the unified TaxDataService class from the new modular structure
from .tax_data import TaxDataService

# Re-export for backward compatibility
__all__ = ['TaxDataService']
