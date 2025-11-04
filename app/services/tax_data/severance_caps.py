"""
Severance payment caps management
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import logging
from .base_service import BaseTaxDataService

logger = logging.getLogger(__name__)

class SeveranceCapsService(BaseTaxDataService):
    """Service for managing severance payment caps"""
    
    @classmethod
    def get_severance_caps(cls) -> List[Dict]:
        """
        Get all severance payment caps by year
        """
        # Get from storage or cache if available
        try:
            # Try to load from storage
            caps = cls._load_severance_caps_from_storage()
            if caps:
                return caps
        except Exception as e:
            logger.warning(f"Failed to load severance caps from storage: {e}")
        
        # Fall back to default values
        return cls._get_default_severance_caps()
    
    @classmethod
    def _load_severance_caps_from_storage(cls) -> List[Dict]:
        """
        Load severance caps from storage (e.g., file, database)
        """
        try:
            # In a real implementation, this would load from a database or file
            # For now, we'll use a simple approach with localStorage in the frontend
            return []
        except Exception as e:
            logger.error(f"Error loading severance caps: {e}")
            return []
    
    @classmethod
    def _get_default_severance_caps(cls) -> List[Dict]:
        """
        Get default severance caps when storage is unavailable
        """
        return [
            {'year': 2025, 'monthly_cap': 13750, 'annual_cap': 13750 * 12, 'description': 'תקרה חודשית לשנת 2025'},
            {'year': 2024, 'monthly_cap': 13750, 'annual_cap': 13750 * 12, 'description': 'תקרה חודשית לשנת 2024'},
            {'year': 2023, 'monthly_cap': 13310, 'annual_cap': 13310 * 12, 'description': 'תקרה חודשית לשנת 2023'},
            {'year': 2022, 'monthly_cap': 12640, 'annual_cap': 12640 * 12, 'description': 'תקרה חודשית לשנת 2022'},
            {'year': 2021, 'monthly_cap': 12340, 'annual_cap': 12340 * 12, 'description': 'תקרה חודשית לשנת 2021'},
            {'year': 2020, 'monthly_cap': 12420, 'annual_cap': 12420 * 12, 'description': 'תקרה חודשית לשנת 2020'},
            {'year': 2019, 'monthly_cap': 12380, 'annual_cap': 12380 * 12, 'description': 'תקרה חודשית לשנת 2019'},
            {'year': 2018, 'monthly_cap': 12230, 'annual_cap': 12230 * 12, 'description': 'תקרה חודשית לשנת 2018'},
            {'year': 2017, 'monthly_cap': 12200, 'annual_cap': 12200 * 12, 'description': 'תקרה חודשית לשנת 2017'},
            {'year': 2016, 'monthly_cap': 12230, 'annual_cap': 12230 * 12, 'description': 'תקרה חודשית לשנת 2016'},
            {'year': 2015, 'monthly_cap': 12340, 'annual_cap': 12340 * 12, 'description': 'תקרה חודשית לשנת 2015'},
            {'year': 2014, 'monthly_cap': 12360, 'annual_cap': 12360 * 12, 'description': 'תקרה חודשית לשנת 2014'},
            {'year': 2013, 'monthly_cap': 12120, 'annual_cap': 12120 * 12, 'description': 'תקרה חודשית לשנת 2013'},
            {'year': 2012, 'monthly_cap': 11950, 'annual_cap': 11950 * 12, 'description': 'תקרה חודשית לשנת 2012'},
            {'year': 2011, 'monthly_cap': 11650, 'annual_cap': 11650 * 12, 'description': 'תקרה חודשית לשנת 2011'},
            {'year': 2010, 'monthly_cap': 11390, 'annual_cap': 11390 * 12, 'description': 'תקרה חודשית לשנת 2010'},
        ]
    
    @classmethod
    def update_severance_caps(cls, caps: List[Dict]) -> bool:
        """
        Update severance caps in storage
        """
        try:
            # In a real implementation, this would save to a database or file
            # For now, we'll use a simple approach with localStorage in the frontend
            logger.info(f"Updated {len(caps)} severance caps")
            return True
        except Exception as e:
            logger.error(f"Error updating severance caps: {e}")
            return False
    
    @classmethod
    def get_current_severance_cap(cls, year: Optional[int] = None) -> Decimal:
        """
        Get current severance payment cap from official sources
        Falls back to known values if API is unavailable
        """
        if year is None:
            year = cls._get_current_year()
            
        # Try to fetch from API first
        api_cap = cls._fetch_severance_cap_from_api(year)
        if api_cap:
            return api_cap
            
        # Get all caps
        caps = cls.get_severance_caps()
        
        # Find cap for specified year
        cap_data = cls._get_data_for_year(caps, year)
        if cap_data:
            return Decimal(str(cap_data['monthly_cap']))
        
        # If not found, use the most recent cap
        recent_cap = cls._get_most_recent_data(caps)
        if recent_cap:
            return Decimal(str(recent_cap['monthly_cap']))
        
        # Absolute fallback
        return Decimal("13750")  # 2025 value
    
    @classmethod
    def _fetch_severance_cap_from_api(cls, year: int) -> Optional[Decimal]:
        """
        Attempt to fetch severance cap from government API
        This is a placeholder - would need actual API endpoint
        """
        # TODO: Implement actual API call when endpoint is available
        # For now, return None to use fallback values
        return None
    
    @classmethod
    def get_severance_exemption_amount(cls, service_years: float, year: Optional[int] = None) -> Decimal:
        """
        Calculate severance exemption amount based on service years and current caps
        """
        if year is None:
            year = cls._get_current_year()
            
        # Get current monthly cap
        monthly_cap = cls.get_current_severance_cap(year)
        
        # Calculate total exemption (monthly cap * service years)
        total_exemption = monthly_cap * Decimal(str(service_years))
        
        return total_exemption
