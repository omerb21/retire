"""
Base service for tax data modules with common utilities
"""
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class BaseTaxDataService:
    """Base class for all tax data services with common functionality"""
    
    @classmethod
    def _get_most_recent_data(cls, data: list, year_key: str = 'year', default=None):
        """Helper to get the most recent data point from a list of dicts with year keys"""
        if not data:
            return default
            
        try:
            sorted_data = sorted(data, key=lambda x: x.get(year_key, 0), reverse=True)
            return sorted_data[0] if sorted_data else default
        except Exception as e:
            logger.warning(f"Error getting most recent data: {e}")
            return default
    
    @classmethod
    def _get_data_for_year(cls, data: list, target_year: int, year_key: str = 'year', default=None):
        """Helper to get data for a specific year from a list of dicts with year keys"""
        if not data:
            return default
            
        try:
            for item in data:
                if item.get(year_key) == target_year:
                    return item
            return default
        except Exception as e:
            logger.warning(f"Error getting data for year {target_year}: {e}")
            return default
    
    @classmethod
    def _get_current_year(cls) -> int:
        """Get current calendar year"""
        return datetime.now().year
