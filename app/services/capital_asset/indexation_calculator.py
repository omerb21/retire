"""Indexation calculator for capital assets."""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Optional

from app.models.capital_asset import IndexationMethod
from app.services.capital_asset.base_calculator import BaseCalculator

logger = logging.getLogger(__name__)


class IndexationCalculator(BaseCalculator):
    """
    מחשבון הצמדה לנכסי הון.
    
    תומך בשיטות הצמדה:
    - NONE: ללא הצמדה
    - FIXED: הצמדה בשיעור קבוע
    - CPI: הצמדה למדד המחירים לצרכן
    """
    
    def __init__(self, cpi_series: Optional[Dict[int, Decimal]] = None):
        """
        אתחול מחשבון ההצמדה.
        
        Args:
            cpi_series: סדרת מדד מחירים לפי שנה (שנה -> ערך מדד)
        """
        self.cpi_series = cpi_series or {}
    
    def calculate(
        self,
        base_amount: Decimal,
        indexation_method: IndexationMethod,
        start_date: date,
        end_date: date,
        fixed_rate: Optional[Decimal] = None
    ) -> Decimal:
        """
        חשב סכום מוצמד.
        
        Args:
            base_amount: סכום בסיס לפני הצמדה
            indexation_method: שיטת ההצמדה
            start_date: תאריך התחלה
            end_date: תאריך סיום
            fixed_rate: שיעור קבוע (נדרש עבור FIXED)
            
        Returns:
            סכום מוצמד
            
        Raises:
            ValueError: אם הפרמטרים לא תקינים
        """
        self.validate_inputs(
            base_amount=base_amount,
            indexation_method=indexation_method,
            start_date=start_date,
            end_date=end_date,
            fixed_rate=fixed_rate
        )
        
        if indexation_method == IndexationMethod.NONE:
            return base_amount
        
        years = self._calculate_years_between(start_date, end_date)
        if years <= 0:
            return base_amount
        
        if indexation_method == IndexationMethod.FIXED:
            return self._calculate_fixed_indexation(base_amount, years, fixed_rate)
        elif indexation_method == IndexationMethod.CPI:
            return self._calculate_cpi_indexation(base_amount, start_date, end_date)
        else:
            raise ValueError(f"Unsupported indexation method: {indexation_method}")
    
    def validate_inputs(
        self,
        base_amount: Decimal,
        indexation_method: IndexationMethod,
        start_date: date,
        end_date: date,
        fixed_rate: Optional[Decimal] = None
    ) -> None:
        """
        אמת פרמטרי קלט.
        
        Raises:
            ValueError: אם הקלט לא תקין
        """
        if base_amount < 0:
            raise ValueError("Base amount cannot be negative")
        
        if end_date < start_date:
            raise ValueError("End date must be after start date")
        
        if indexation_method == IndexationMethod.FIXED and fixed_rate is None:
            raise ValueError("Fixed rate is required for fixed indexation")
    
    def _calculate_fixed_indexation(
        self,
        amount: Decimal,
        years: int,
        rate: Optional[Decimal]
    ) -> Decimal:
        """
        חשב הצמדה בשיעור קבוע.
        
        Args:
            amount: סכום בסיס
            years: מספר שנים
            rate: שיעור הצמדה שנתי
            
        Returns:
            סכום מוצמד
        """
        if rate is None:
            raise ValueError("Fixed rate is required for fixed indexation")
        
        indexation_factor = (Decimal('1') + rate) ** years
        indexed_amount = amount * indexation_factor
        
        logger.debug(
            f"Fixed indexation: amount={amount}, years={years}, "
            f"rate={rate}, factor={indexation_factor}, result={indexed_amount}"
        )
        
        return indexed_amount
    
    def _calculate_cpi_indexation(
        self,
        amount: Decimal,
        start_date: date,
        end_date: date
    ) -> Decimal:
        """
        חשב הצמדה למדד המחירים לצרכן.
        
        Args:
            amount: סכום בסיס
            start_date: תאריך התחלה
            end_date: תאריך סיום
            
        Returns:
            סכום מוצמד
        """
        cpi_factor = self._get_cpi_factor(start_date, end_date)
        indexed_amount = amount * cpi_factor
        
        logger.debug(
            f"CPI indexation: amount={amount}, "
            f"start={start_date}, end={end_date}, "
            f"factor={cpi_factor}, result={indexed_amount}"
        )
        
        return indexed_amount
    
    def _get_cpi_factor(self, start_date: date, end_date: date) -> Decimal:
        """
        חשב מקדם הצמדה למדד.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            
        Returns:
            מקדם הצמדה (1.0 אם אין נתונים)
        """
        start_year = start_date.year
        end_year = end_date.year
        
        # אם אותה שנה או אין נתונים - אין הצמדה
        if (start_year == end_year or
            start_year not in self.cpi_series or
            end_year not in self.cpi_series):
            return Decimal('1')
        
        start_cpi = self.cpi_series[start_year]
        end_cpi = self.cpi_series[end_year]
        
        if start_cpi <= 0:
            logger.warning(f"Invalid start CPI value: {start_cpi}")
            return Decimal('1')
        
        factor = end_cpi / start_cpi
        
        logger.debug(
            f"CPI factor calculation: {start_year}={start_cpi}, "
            f"{end_year}={end_cpi}, factor={factor}"
        )
        
        return factor
    
    def _calculate_years_between(self, start_date: date, end_date: date) -> int:
        """
        חשב מספר שנים שלמות בין שני תאריכים.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            
        Returns:
            מספר שנים שלמות
        """
        if end_date <= start_date:
            return 0
        
        years = end_date.year - start_date.year
        
        # אם עוד לא הגענו ליום השנה, הפחת שנה
        if (end_date.month, end_date.day) < (start_date.month, start_date.day):
            years -= 1
        
        return max(0, years)
