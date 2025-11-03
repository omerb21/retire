"""Main service for capital asset calculations and management."""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.schemas.capital_asset import CapitalAssetCashflowItem
from app.providers.tax_params import TaxParamsProvider, InMemoryTaxParamsProvider
from app.services.capital_asset.indexation_calculator import IndexationCalculator
from app.services.capital_asset.tax_calculator import TaxCalculator
from app.services.capital_asset.payment_calculator import PaymentCalculator
from app.services.capital_asset.cashflow_calculator import CashflowCalculator

logger = logging.getLogger(__name__)


class CapitalAssetService:
    """
    שירות מרכזי לניהול וחישוב נכסי הון.
    
    משמש כ-Facade לכל המחשבונים המודולריים:
    - IndexationCalculator: חישובי הצמדה
    - TaxCalculator: חישובי מס
    - PaymentCalculator: לוחות תשלומים
    - CashflowCalculator: תזרים מזומנים
    
    תואם לחלוטין לממשק המקורי של CapitalAssetService.
    """
    
    def __init__(self, tax_params_provider: Optional[TaxParamsProvider] = None):
        """
        אתחול השירות עם ספק פרמטרי מס.
        
        Args:
            tax_params_provider: ספק פרמטרי מס (ברירת מחדל: InMemory)
        """
        self.tax_params_provider = tax_params_provider or InMemoryTaxParamsProvider()
        self._initialize_calculators()
    
    def _initialize_calculators(self):
        """אתחול כל המחשבונים."""
        tax_params = self.tax_params_provider.get_params()
        
        # מחשבון הצמדה
        self.indexation_calculator = IndexationCalculator(
            cpi_series=tax_params.cpi_series
        )
        
        # מחשבון מס
        self.tax_calculator = TaxCalculator(
            tax_brackets=self._prepare_tax_brackets(tax_params)
        )
        
        # מחשבון תשלומים
        self.payment_calculator = PaymentCalculator()
        
        # מחשבון תזרים
        self.cashflow_calculator = CashflowCalculator(
            indexation_calculator=self.indexation_calculator,
            tax_calculator=self.tax_calculator
        )
        
        logger.debug("Capital asset calculators initialized successfully")
    
    def _prepare_tax_brackets(
        self,
        tax_params
    ) -> List[Tuple[Optional[Decimal], Decimal]]:
        """
        הכן מדרגות מס מפרמטרי המס.
        
        Args:
            tax_params: פרמטרי מס
            
        Returns:
            רשימת טאפלים של (סף_עליון, שיעור_מס)
        """
        brackets = []
        for bracket in tax_params.income_tax_brackets:
            max_income = (
                Decimal(str(bracket.max_income))
                if bracket.max_income
                else None
            )
            rate = Decimal(str(bracket.rate))
            brackets.append((max_income, rate))
        
        logger.debug(f"Prepared {len(brackets)} tax brackets")
        return brackets
    
    # ============================================================
    # Public API Methods - תואם לממשק המקורי
    # ============================================================
    
    def project_cashflow(
        self,
        asset: CapitalAsset,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[CapitalAssetCashflowItem]:
        """
        צור תחזית תזרים מזומנים לנכס הון.
        
        Args:
            asset: נכס ההון
            start_date: תאריך התחלה
            end_date: תאריך סיום
            reference_date: תאריך ייחוס להצמדה
            
        Returns:
            רשימת פריטי תזרים מזומנים
        """
        return self.cashflow_calculator.calculate(
            asset=asset,
            start_date=start_date,
            end_date=end_date,
            reference_date=reference_date
        )
    
    def generate_combined_cashflow(
        self,
        db_session: Session,
        client_id: int,
        start_date: date,
        end_date: date,
        reference_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        צור תזרים מזומנים משולב לכל נכסי ההון של הלקוח.
        
        Args:
            db_session: סשן מסד נתונים
            client_id: מזהה לקוח
            start_date: תאריך התחלה
            end_date: תאריך סיום
            reference_date: תאריך ייחוס
            
        Returns:
            רשימת פריטי תזרים מצטברים לפי תאריך
        """
        logger.debug(
            f"Generating combined capital asset cashflow for client {client_id}"
        )
        
        # שלוף את כל נכסי ההון של הלקוח
        assets = db_session.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id
        ).all()
        
        if not assets:
            logger.debug("No capital assets found for client")
            return []
        
        # צור תזרים לכל נכס
        all_cashflow_items = []
        for asset in assets:
            cashflow_items = self.project_cashflow(
                asset, start_date, end_date, reference_date
            )
            all_cashflow_items.extend(cashflow_items)
        
        # צבור לפי תאריך
        aggregated_cashflow = {}
        for item in all_cashflow_items:
            date_key = item.date
            if date_key not in aggregated_cashflow:
                aggregated_cashflow[date_key] = {
                    'date': date_key,
                    'gross_return': Decimal('0'),
                    'tax_amount': Decimal('0'),
                    'net_return': Decimal('0')
                }
            
            aggregated_cashflow[date_key]['gross_return'] += item.gross_return
            aggregated_cashflow[date_key]['tax_amount'] += item.tax_amount
            aggregated_cashflow[date_key]['net_return'] += item.net_return
        
        # המר לרשימה ממוינת
        result = sorted(aggregated_cashflow.values(), key=lambda x: x['date'])
        logger.debug(f"Generated {len(result)} aggregated cashflow items")
        return result
    
    # ============================================================
    # Additional Helper Methods - תואם לממשק המקורי
    # ============================================================
    
    def apply_indexation(
        self,
        base_return: Decimal,
        asset: CapitalAsset,
        target_date: date,
        reference_date: Optional[date] = None
    ) -> Decimal:
        """
        החל הצמדה על סכום בסיס.
        
        Args:
            base_return: סכום בסיס
            asset: נכס ההון
            target_date: תאריך יעד
            reference_date: תאריך ייחוס
            
        Returns:
            סכום מוצמד
        """
        return self.indexation_calculator.calculate(
            base_amount=base_return,
            indexation_method=asset.indexation_method,
            start_date=reference_date or asset.start_date,
            end_date=target_date,
            fixed_rate=asset.fixed_rate
        )
    
    def calculate_tax(self, gross_return: Decimal, asset: CapitalAsset) -> Decimal:
        """
        חשב מס על תשואה ברוטו.
        
        הערה: עבור TAXABLE ו-TAX_SPREAD, המס מחושב ב-Frontend
        באמצעות מדרגות מס שוליות. פונקציה זו מחזירה 0 למקרים אלו.
        
        Args:
            gross_return: תשואה ברוטו
            asset: נכס ההון
            
        Returns:
            סכום המס
        """
        tax_result = self.tax_calculator.calculate(
            gross_amount=gross_return,
            tax_treatment=asset.tax_treatment,
            tax_rate=asset.tax_rate,
            spread_years=getattr(asset, 'spread_years', None)
        )
        
        return tax_result['total_tax']
    
    def calculate_spread_tax(
        self,
        taxable_amount: Decimal,
        spread_years: int,
        annual_regular_income: Decimal = Decimal('0')
    ) -> Dict[str, Any]:
        """
        חשב מס עם פריסה על מספר שנים.
        
        Args:
            taxable_amount: סכום כולל חייב במס
            spread_years: מספר שנות פריסה
            annual_regular_income: הכנסה שנתית רגילה
            
        Returns:
            Dict עם total_tax, annual_portion, yearly_taxes
        """
        from app.models.capital_asset import TaxTreatment
        
        return self.tax_calculator.calculate(
            gross_amount=taxable_amount,
            tax_treatment=TaxTreatment.TAX_SPREAD,
            spread_years=spread_years,
            annual_regular_income=annual_regular_income
        )
    
    def calculate_monthly_return(self, asset: CapitalAsset) -> Decimal:
        """
        חשב תשואה חודשית על בסיס תדירות התשלום.
        
        Args:
            asset: נכס ההון
            
        Returns:
            תשואה חודשית
        """
        return self.payment_calculator.calculate_period_return(
            total_value=asset.current_value,
            annual_return_rate=asset.annual_return_rate,
            frequency=asset.payment_frequency
        )
    
    # ============================================================
    # Private Helper Methods - תואם לממשק המקורי
    # ============================================================
    
    def _calculate_years_between(self, start_date: date, end_date: date) -> int:
        """חשב שנים שלמות בין תאריכים."""
        return self.indexation_calculator._calculate_years_between(
            start_date, end_date
        )
    
    def _calculate_cpi_factor(
        self,
        cpi_series: Dict[int, Decimal],
        start_date: date,
        end_date: date
    ) -> Decimal:
        """חשב מקדם הצמדה למדד."""
        return self.indexation_calculator._get_cpi_factor(start_date, end_date)
    
    def _align_to_first_of_month(self, target_date: date) -> date:
        """יישר תאריך לתחילת החודש."""
        return self.cashflow_calculator._align_to_first_of_month(target_date)
    
    def _get_payment_interval(self, frequency) -> int:
        """קבל מרווח תשלום בחודשים."""
        return self.payment_calculator.get_payment_interval_months(frequency)
    
    def _is_payment_date(self, current_date: date, start_date: date, frequency) -> bool:
        """בדוק אם תאריך הוא תאריך תשלום."""
        return self.payment_calculator.is_payment_date(
            current_date, start_date, frequency
        )
    
    def _calculate_period_return(self, asset: CapitalAsset, payment_date: date) -> Decimal:
        """חשב תשואה לתקופה ספציפית."""
        return self.payment_calculator.calculate_period_return(
            total_value=asset.current_value,
            annual_return_rate=asset.annual_return_rate,
            frequency=asset.payment_frequency
        )
    
    def _add_months(self, target_date: date, months: int) -> date:
        """הוסף חודשים לתאריך."""
        return self.payment_calculator._add_months(target_date, months)
    
    def _calculate_tax_by_brackets(self, taxable_income: Decimal) -> Decimal:
        """חשב מס לפי מדרגות."""
        return self.tax_calculator._calculate_tax_by_brackets(taxable_income)
