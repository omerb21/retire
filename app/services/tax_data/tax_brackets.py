"""
Tax brackets management service
"""
from typing import Dict, List
import logging
from .base_service import BaseTaxDataService

logger = logging.getLogger(__name__)

class TaxBracketsService(BaseTaxDataService):
    """Service for managing tax brackets"""
    
    @staticmethod
    def get_tax_brackets(year: int) -> List[Dict]:
        """
        Get tax brackets for the specified year from Tax Authority or fallback data
        """
        try:
            # In production, this would fetch from Israeli Tax Authority API
            # For now, use accurate historical data
            pass
        except Exception as e:
            logger.warning(f"Error fetching tax brackets: {e}")
        
        # Use accurate tax brackets based on year
        return TaxBracketsService._get_tax_brackets_by_year(year)
    
    @staticmethod
    def _get_tax_brackets_by_year(year: int) -> List[Dict]:
        """
        Get tax brackets for specific year - based on actual Israeli tax law
        """
        if year >= 2024:
            # 2024-2025 tax brackets (in NIS)
            return [
                {'min_income': 0, 'max_income': 81480, 'rate': 0.10, 'description': 'מדרגה ראשונה - 10%'},
                {'min_income': 81481, 'max_income': 116760, 'rate': 0.14, 'description': 'מדרגה שנייה - 14%'},
                {'min_income': 116761, 'max_income': 187440, 'rate': 0.20, 'description': 'מדרגה שלישית - 20%'},
                {'min_income': 187441, 'max_income': 241680, 'rate': 0.31, 'description': 'מדרגה רביעית - 31%'},
                {'min_income': 241681, 'max_income': 498360, 'rate': 0.35, 'description': 'מדרגה חמישית - 35%'},
                {'min_income': 498361, 'max_income': 663240, 'rate': 0.47, 'description': 'מדרגה שישית - 47%'},
                {'min_income': 663241, 'max_income': 999999999, 'rate': 0.50, 'description': 'מדרגה עליונה - 50%'}
            ]
        elif year >= 2023:
            # 2023 tax brackets
            return [
                {'min_income': 0, 'max_income': 77400, 'rate': 0.10, 'description': 'מדרגה ראשונה - 10%'},
                {'min_income': 77401, 'max_income': 110880, 'rate': 0.14, 'description': 'מדרגה שנייה - 14%'},
                {'min_income': 110881, 'max_income': 177840, 'rate': 0.20, 'description': 'מדרגה שלישית - 20%'},
                {'min_income': 177841, 'max_income': 229320, 'rate': 0.31, 'description': 'מדרגה רביעית - 31%'},
                {'min_income': 229321, 'max_income': 472920, 'rate': 0.35, 'description': 'מדרגה חמישית - 35%'},
                {'min_income': 472921, 'max_income': 630240, 'rate': 0.47, 'description': 'מדרגה שישית - 47%'},
                {'min_income': 630241, 'max_income': 999999999, 'rate': 0.50, 'description': 'מדרגה עליונה - 50%'}
            ]
        else:
            # Default to 2024 brackets for older years
            return TaxBracketsService._get_tax_brackets_by_year(2024)
