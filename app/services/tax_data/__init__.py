"""
Tax Data Service - Modular tax data management
"""

# Import all services
from .base_service import BaseTaxDataService
from .severance_caps import SeveranceCapsService
from .cpi_service import CPIService
from .tax_brackets import TaxBracketsService
from .indexation import IndexationService
from .cache_manager import CacheManager

# Export all services
__all__ = [
    'BaseTaxDataService',
    'SeveranceCapsService',
    'CPIService',
    'TaxBracketsService',
    'IndexationService',
    'CacheManager',
    'TaxDataService'  # Backward compatibility class
]

# Backward compatibility: TaxDataService class that delegates to individual services
class TaxDataService:
    """
    Unified interface for tax data services - maintains backward compatibility
    Delegates to individual specialized services
    """
    
    # CBS API endpoints (for backward compatibility)
    CBS_BASE_URL = CPIService.CBS_BASE_URL
    CBS_CPI_ENDPOINT = CPIService.CBS_CPI_ENDPOINT
    GOV_IL_BASE = "https://www.gov.il"
    
    # Severance caps methods
    @classmethod
    def get_severance_caps(cls):
        """Get all severance payment caps by year"""
        return SeveranceCapsService.get_severance_caps()
    
    @classmethod
    def _load_severance_caps_from_storage(cls):
        """Load severance caps from storage"""
        return SeveranceCapsService._load_severance_caps_from_storage()
    
    @classmethod
    def _get_default_severance_caps(cls):
        """Get default severance caps"""
        return SeveranceCapsService._get_default_severance_caps()
    
    @classmethod
    def update_severance_caps(cls, caps):
        """Update severance caps in storage"""
        return SeveranceCapsService.update_severance_caps(caps)
    
    @classmethod
    def get_current_severance_cap(cls, year=None):
        """Get current severance payment cap"""
        return SeveranceCapsService.get_current_severance_cap(year)
    
    @classmethod
    def _fetch_severance_cap_from_api(cls, year):
        """Fetch severance cap from API"""
        return SeveranceCapsService._fetch_severance_cap_from_api(year)
    
    @classmethod
    def get_severance_exemption_amount(cls, service_years, year=None):
        """Calculate severance exemption amount"""
        return SeveranceCapsService.get_severance_exemption_amount(service_years, year)
    
    # CPI methods
    @staticmethod
    def get_cpi_data(start_year, end_year):
        """Get CPI data"""
        return CPIService.get_cpi_data(start_year, end_year)
    
    @staticmethod
    def _get_fallback_cpi_data(start_year, end_year):
        """Get fallback CPI data"""
        return CPIService._get_fallback_cpi_data(start_year, end_year)
    
    # Indexation methods
    @classmethod
    def calculate_indexation_factor(cls, base_year, target_year):
        """Calculate indexation factor"""
        return IndexationService.calculate_indexation_factor(base_year, target_year)
    
    # Tax brackets methods
    @staticmethod
    def get_tax_brackets(year):
        """Get tax brackets for year"""
        return TaxBracketsService.get_tax_brackets(year)
    
    @staticmethod
    def _get_tax_brackets_by_year(year):
        """Get tax brackets by year"""
        return TaxBracketsService._get_tax_brackets_by_year(year)
    
    # Cache management methods
    @classmethod
    def update_tax_data_cache(cls):
        """Update tax data cache"""
        return CacheManager.update_tax_data_cache()
