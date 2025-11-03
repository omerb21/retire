"""Cashflow calculator for capital assets."""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.models.capital_asset import CapitalAsset
from app.schemas.capital_asset import CapitalAssetCashflowItem
from app.services.capital_asset.base_calculator import BaseCalculator
from app.services.capital_asset.indexation_calculator import IndexationCalculator
from app.services.capital_asset.tax_calculator import TaxCalculator

logger = logging.getLogger(__name__)


class CashflowCalculator(BaseCalculator):
    """
    מחשבון תזרים מזומנים לנכסי הון.
    
    אחראי על:
    - יצירת תחזיות תזרים מזומנים
    - שילוב הצמדה ומס
    - חישוב ברוטו/נטו
    
    הערה חשובה:
    נכסי הון הם תמיד תשלום חד פעמי בתאריך ההתחלה.
    """
    
    def __init__(
        self,
        indexation_calculator: IndexationCalculator,
        tax_calculator: TaxCalculator
    ):
        """
        אתחול מחשבון התזרים.
        
        Args:
            indexation_calculator: מחשבון הצמדה
            tax_calculator: מחשבון מס
        """
        self.indexation_calculator = indexation_calculator
        self.tax_calculator = tax_calculator
    
    def calculate(
        self,
        asset: CapitalAsset,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[CapitalAssetCashflowItem]:
        """
        צור תזרים מזומנים לנכס הון.
        
        נכסי הון הם תמיד תשלום חד פעמי.
        יחס המס מיושם באופן אחיד ללא קשר ל-spread_years.
        
        Args:
            asset: נכס ההון
            start_date: תאריך התחלה לתחזית
            end_date: תאריך סיום לתחזית
            reference_date: תאריך ייחוס להצמדה (אופציונלי)
            
        Returns:
            רשימת פריטי תזרים מזומנים
        """
        logger.debug(
            f"Projecting cashflow for asset {asset.id} "
            f"from {start_date} to {end_date}"
        )
        
        # נכסי הון הם תמיד תשלום חד פעמי
        payment_date = self._align_to_first_of_month(asset.start_date)
        
        # בדוק אם התשלום בטווח התאריכים
        if not (start_date <= payment_date <= end_date):
            logger.debug(
                f"Payment date {payment_date} outside range "
                f"{start_date} to {end_date}"
            )
            return []
        
        # סכום ברוטו
        gross_amount = asset.current_value
        
        # הצמדה אם נדרשת
        indexed_amount = self.indexation_calculator.calculate(
            base_amount=gross_amount,
            indexation_method=asset.indexation_method,
            start_date=reference_date or asset.start_date,
            end_date=payment_date,
            fixed_rate=asset.fixed_rate
        )
        
        # חישוב מס (אחיד לכל סוגי הנכסים)
        tax_result = self.tax_calculator.calculate(
            gross_amount=indexed_amount,
            tax_treatment=asset.tax_treatment,
            tax_rate=asset.tax_rate,
            spread_years=getattr(asset, 'spread_years', None)
        )
        
        tax_amount = tax_result['total_tax']
        net_amount = indexed_amount - tax_amount
        
        # יצירת פריט תזרים
        cashflow_item = CapitalAssetCashflowItem(
            date=payment_date,
            gross_return=indexed_amount,
            tax_amount=tax_amount,
            net_return=net_amount,
            asset_type=asset.asset_type,
            description=asset.description or f"תשלום חד פעמי - {asset.asset_type}"
        )
        
        logger.debug(
            f"Generated cashflow item: date={payment_date}, "
            f"gross={indexed_amount}, tax={tax_amount}, net={net_amount}"
        )
        
        return [cashflow_item]
    
    def calculate_with_details(
        self,
        asset: CapitalAsset,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> dict:
        """
        צור תזרים עם פרטים נוספים.
        
        Args:
            asset: נכס ההון
            start_date: תאריך התחלה
            end_date: תאריך סיום
            reference_date: תאריך ייחוס
            
        Returns:
            Dict עם:
            - cashflow: רשימת פריטי תזרים
            - total_gross: סה"כ ברוטו
            - total_tax: סה"כ מס
            - total_net: סה"כ נטו
            - payment_count: מספר תשלומים
        """
        cashflow_items = self.calculate(
            asset=asset,
            start_date=start_date,
            end_date=end_date,
            reference_date=reference_date
        )
        
        total_gross = sum(item.gross_return for item in cashflow_items)
        total_tax = sum(item.tax_amount for item in cashflow_items)
        total_net = sum(item.net_return for item in cashflow_items)
        
        return {
            'cashflow': cashflow_items,
            'total_gross': total_gross,
            'total_tax': total_tax,
            'total_net': total_net,
            'payment_count': len(cashflow_items)
        }
    
    def _align_to_first_of_month(self, target_date: date) -> date:
        """
        יישר תאריך לתחילת החודש.
        
        Args:
            target_date: תאריך ליישור
            
        Returns:
            תאריך מיושר ל-1 בחודש
        """
        return date(target_date.year, target_date.month, 1)
