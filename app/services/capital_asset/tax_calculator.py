"""Tax calculator for capital assets."""

import logging
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple

from app.models.capital_asset import TaxTreatment
from app.services.capital_asset.base_calculator import BaseCalculator

logger = logging.getLogger(__name__)


class TaxCalculator(BaseCalculator):
    """
    מחשבון מס לנכסי הון.
    
    תומך ביחסי מס:
    - EXEMPT: פטור ממס
    - FIXED_RATE: מס בשיעור קבוע (25%)
    - TAXABLE: חייב במס שולי (מחושב ב-Frontend)
    - TAX_SPREAD: פריסת מס על מספר שנים
    
    הערה חשובה:
    עבור TAXABLE ו-TAX_SPREAD, המס מחושב ב-Frontend באמצעות מדרגות מס שוליות.
    הפונקציה כאן מחזירה 0 כדי למנוע כפילות מס.
    """
    
    def __init__(self, tax_brackets: Optional[List[Tuple[Optional[Decimal], Decimal]]] = None):
        """
        אתחול מחשבון המס.
        
        Args:
            tax_brackets: רשימת מדרגות מס [(סף_עליון, שיעור_מס), ...]
                         None בסף העליון = מדרגה אחרונה
        """
        self.tax_brackets = tax_brackets or []
    
    def calculate(
        self,
        gross_amount: Decimal,
        tax_treatment: TaxTreatment,
        tax_rate: Optional[Decimal] = None,
        spread_years: Optional[int] = None,
        annual_regular_income: Decimal = Decimal('0')
    ) -> Dict[str, Any]:
        """
        חשב מס על נכס הון.
        
        Args:
            gross_amount: סכום ברוטו
            tax_treatment: יחס מס
            tax_rate: שיעור מס קבוע (נדרש עבור FIXED_RATE)
            spread_years: מספר שנות פריסה (נדרש עבור TAX_SPREAD)
            annual_regular_income: הכנסה שנתית רגילה
            
        Returns:
            Dict עם:
            - total_tax: סכום מס כולל
            - annual_tax: מס שנתי (לפריסה)
            - annual_portion: חלק שנתי מהסכום (לפריסה)
            - yearly_taxes: רשימת מס לכל שנה (לפריסה)
            
        Raises:
            ValueError: אם הפרמטרים לא תקינים
        """
        self.validate_inputs(
            gross_amount=gross_amount,
            tax_treatment=tax_treatment,
            tax_rate=tax_rate,
            spread_years=spread_years
        )
        
        if tax_treatment == TaxTreatment.EXEMPT:
            return self._calculate_exempt()
        elif tax_treatment == TaxTreatment.FIXED_RATE:
            return self._calculate_fixed_rate(gross_amount, tax_rate)
        elif tax_treatment == TaxTreatment.TAXABLE:
            return self._calculate_taxable(gross_amount)
        elif tax_treatment == TaxTreatment.TAX_SPREAD:
            return self._calculate_spread_tax(gross_amount, spread_years, annual_regular_income)
        else:
            raise ValueError(f"Unsupported tax treatment: {tax_treatment}")
    
    def validate_inputs(
        self,
        gross_amount: Decimal,
        tax_treatment: TaxTreatment,
        tax_rate: Optional[Decimal] = None,
        spread_years: Optional[int] = None
    ) -> None:
        """
        אמת פרמטרי קלט.
        
        Raises:
            ValueError: אם הקלט לא תקין
        """
        if gross_amount < 0:
            raise ValueError("Gross amount cannot be negative")
        
        if tax_treatment == TaxTreatment.FIXED_RATE and tax_rate is None:
            raise ValueError("Tax rate is required for fixed rate tax")
        
        if tax_treatment == TaxTreatment.TAX_SPREAD and (spread_years is None or spread_years <= 0):
            raise ValueError("Spread years must be positive for tax spread")
    
    def _calculate_exempt(self) -> Dict[str, Any]:
        """
        חשב מס לנכס פטור ממס.
        
        Returns:
            Dict עם מס = 0
        """
        return {
            'total_tax': Decimal('0'),
            'annual_tax': Decimal('0'),
            'yearly_taxes': []
        }
    
    def _calculate_fixed_rate(
        self,
        amount: Decimal,
        rate: Optional[Decimal]
    ) -> Dict[str, Any]:
        """
        חשב מס בשיעור קבוע.
        
        Args:
            amount: סכום ברוטו
            rate: שיעור מס
            
        Returns:
            Dict עם סכום המס
        """
        if rate is None:
            raise ValueError("Tax rate is required for fixed rate tax")
        
        total_tax = amount * rate
        
        logger.debug(f"Fixed rate tax: amount={amount}, rate={rate}, tax={total_tax}")
        
        return {
            'total_tax': total_tax,
            'annual_tax': total_tax,
            'yearly_taxes': [total_tax]
        }
    
    def _calculate_taxable(self, amount: Decimal) -> Dict[str, Any]:
        """
        חשב מס חייב במס רגיל.
        
        הערה: המס מחושב ב-Frontend באמצעות מדרגות מס שוליות.
        מחזיר 0 כדי למנוע כפילות מס.
        
        Args:
            amount: סכום ברוטו
            
        Returns:
            Dict עם מס = 0 (המס מחושב ב-Frontend)
        """
        logger.debug(
            f"Taxable asset: amount={amount}, "
            f"tax calculated in frontend using marginal rates"
        )
        
        return {
            'total_tax': Decimal('0'),
            'annual_tax': Decimal('0'),
            'yearly_taxes': []
        }
    
    def _calculate_spread_tax(
        self,
        taxable_amount: Decimal,
        spread_years: int,
        annual_regular_income: Decimal = Decimal('0')
    ) -> Dict[str, Any]:
        """
        חשב מס עם פריסה על מספר שנים.
        
        לוגיקה מיוחדת לפיצויי פיטורין:
        - מחלק את הסכום באופן שווה על מספר השנים
        - מחשב מס שנתי על החלק השנתי
        - סה"כ מס = מס שנתי × מספר שנים
        
        Args:
            taxable_amount: סכום כולל חייב במס
            spread_years: מספר שנות פריסה
            annual_regular_income: הכנסה שנתית רגילה (לא בשימוש כרגע)
            
        Returns:
            Dict עם:
            - total_tax: סכום מס כולל
            - annual_portion: חלק שנתי מהסכום
            - annual_tax: מס שנתי
            - yearly_taxes: רשימת מס לכל שנה
        """
        if spread_years <= 0:
            raise ValueError("Spread years must be positive")
        
        # חלוקה שווה של הסכום על השנים
        annual_portion = taxable_amount / Decimal(spread_years)
        
        # חישוב מס שנתי על החלק השנתי
        annual_tax = self._calculate_tax_by_brackets(annual_portion)
        
        # סה"כ מס = מס שנתי × מספר שנים
        total_spread_tax = annual_tax * Decimal(spread_years)
        
        # רשימת מס לכל שנה (אותו סכום בכל שנה)
        yearly_taxes = [annual_tax] * spread_years
        
        logger.info(
            f"📊 TAX SPREAD CALCULATION: "
            f"total_amount={taxable_amount}, spread_years={spread_years}, "
            f"annual_portion={annual_portion}, annual_tax={annual_tax}, "
            f"total_tax={total_spread_tax}"
        )
        
        return {
            'total_tax': total_spread_tax,
            'annual_portion': annual_portion,
            'annual_tax': annual_tax,
            'yearly_taxes': yearly_taxes
        }
    
    def _calculate_tax_by_brackets(self, taxable_income: Decimal) -> Decimal:
        """
        חשב מס לפי מדרגות מס ישראליות.
        
        Args:
            taxable_income: הכנסה חייבת במס
            
        Returns:
            סכום המס
        """
        if taxable_income <= 0:
            return Decimal('0')
        
        if not self.tax_brackets:
            logger.warning("No tax brackets defined, using TaxConstants")
            # שימוש במדרגות המס הרשמיות מ-TaxConstants
            from app.services.tax.constants import TaxConstants
            tax_brackets_data = TaxConstants.INCOME_TAX_BRACKETS_2025
            
            brackets = [
                (Decimal(str(bracket.max_income)) if bracket.max_income else None,
                 Decimal(str(bracket.rate)))
                for bracket in tax_brackets_data
            ]
        else:
            brackets = self.tax_brackets
        
        total_tax = Decimal('0')
        remaining_income = taxable_income
        prev_threshold = Decimal('0')
        
        for threshold, rate in brackets:
            if threshold is None:
                # מדרגה אחרונה - כל מה שנשאר
                total_tax += remaining_income * rate
                break
            
            if remaining_income <= 0:
                break
            
            # חישוב הכנסה במדרגה הנוכחית
            income_in_bracket = min(remaining_income, threshold - prev_threshold)
            total_tax += income_in_bracket * rate
            remaining_income -= income_in_bracket
            prev_threshold = threshold
        
        logger.debug(
            f"Tax by brackets: income={taxable_income}, tax={total_tax}, "
            f"effective_rate={total_tax / taxable_income if taxable_income > 0 else 0}"
        )
        
        return total_tax
