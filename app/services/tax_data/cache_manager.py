"""
Tax data cache management service
"""
from typing import Dict
from datetime import datetime
from decimal import Decimal
import logging
from .base_service import BaseTaxDataService
from .severance_caps import SeveranceCapsService
from .cpi_service import CPIService
from .tax_brackets import TaxBracketsService

logger = logging.getLogger(__name__)

class CacheManager(BaseTaxDataService):
    """Service for managing tax data cache"""
    
    @classmethod
    def update_tax_data_cache(cls) -> Dict[str, any]:
        """
        Update cached tax data from all sources
        Returns summary of updated data
        """
        current_year = cls._get_current_year()
        
        try:
            # Update severance caps
            severance_cap = SeveranceCapsService.get_current_severance_cap(current_year)
            
            # Update CPI data (last 5 years)
            cpi_data = CPIService.get_cpi_data(current_year - 5, current_year)
            
            # Update tax brackets
            tax_brackets = TaxBracketsService.get_tax_brackets(current_year)
            
            summary = {
                "updated_at": datetime.utcnow().isoformat(),
                "severance_cap": float(severance_cap),
                "cpi_records_count": len(cpi_data),
                "tax_brackets_count": len(tax_brackets),
                "status": "success"
            }
            
            logger.info(f"Tax data cache updated successfully: {summary}")
            return summary
            
        except Exception as e:
            error_summary = {
                "updated_at": datetime.utcnow().isoformat(),
                "status": "error",
                "error": str(e)
            }
            logger.error(f"Failed to update tax data cache: {e}")
            return error_summary
