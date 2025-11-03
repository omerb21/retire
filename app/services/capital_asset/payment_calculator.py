"""Payment calculator for capital assets."""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Tuple
from dateutil.relativedelta import relativedelta

from app.models.capital_asset import PaymentFrequency
from app.services.capital_asset.base_calculator import BaseCalculator

logger = logging.getLogger(__name__)


class PaymentCalculator(BaseCalculator):
    """
    מחשבון לוחות תשלומים לנכסי הון.
    
    תומך בתדירויות תשלום:
    - MONTHLY: חודשי
    - QUARTERLY: רבעוני
    - ANNUALLY: שנתי
    
    הערה: נכסי הון בפועל הם תמיד תשלום חד פעמי.
    מחלקה זו נשמרת לתמיכה עתידית בנכסים מניבים.
    """
    
    def calculate(
        self,
        start_date: date,
        end_date: date,
        frequency: PaymentFrequency,
        amount: Decimal
    ) -> List[Tuple[date, Decimal]]:
        """
        צור לוח תשלומים.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            frequency: תדירות תשלום
            amount: סכום לתשלום
            
        Returns:
            רשימת טאפלים של (תאריך, סכום)
            
        Raises:
            ValueError: אם הפרמטרים לא תקינים
        """
        self.validate_inputs(
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            amount=amount
        )
        
        if frequency == PaymentFrequency.MONTHLY:
            return self._generate_monthly_payments(start_date, end_date, amount)
        elif frequency == PaymentFrequency.QUARTERLY:
            return self._generate_quarterly_payments(start_date, end_date, amount)
        elif frequency == PaymentFrequency.ANNUALLY:
            return self._generate_annual_payments(start_date, end_date, amount)
        else:
            raise ValueError(f"Unsupported payment frequency: {frequency}")
    
    def validate_inputs(
        self,
        start_date: date,
        end_date: date,
        frequency: PaymentFrequency,
        amount: Decimal
    ) -> None:
        """
        אמת פרמטרי קלט.
        
        Raises:
            ValueError: אם הקלט לא תקין
        """
        if end_date < start_date:
            raise ValueError("End date must be after start date")
        
        if amount < 0:
            raise ValueError("Amount cannot be negative")
    
    def _generate_monthly_payments(
        self,
        start_date: date,
        end_date: date,
        amount: Decimal
    ) -> List[Tuple[date, Decimal]]:
        """
        צור תשלומים חודשיים.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            amount: סכום חודשי
            
        Returns:
            רשימת תשלומים חודשיים
        """
        payments = []
        current_date = self._align_to_first_of_month(start_date)
        
        while current_date <= end_date:
            payments.append((current_date, amount))
            current_date = self._add_months(current_date, 1)
        
        logger.debug(f"Generated {len(payments)} monthly payments")
        return payments
    
    def _generate_quarterly_payments(
        self,
        start_date: date,
        end_date: date,
        amount: Decimal
    ) -> List[Tuple[date, Decimal]]:
        """
        צור תשלומים רבעוניים.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            amount: סכום רבעוני
            
        Returns:
            רשימת תשלומים רבעוניים
        """
        payments = []
        current_date = self._align_to_first_of_month(start_date)
        
        while current_date <= end_date:
            payments.append((current_date, amount))
            current_date = self._add_months(current_date, 3)
        
        logger.debug(f"Generated {len(payments)} quarterly payments")
        return payments
    
    def _generate_annual_payments(
        self,
        start_date: date,
        end_date: date,
        amount: Decimal
    ) -> List[Tuple[date, Decimal]]:
        """
        צור תשלומים שנתיים.
        
        Args:
            start_date: תאריך התחלה
            end_date: תאריך סיום
            amount: סכום שנתי
            
        Returns:
            רשימת תשלומים שנתיים
        """
        payments = []
        current_date = self._align_to_first_of_month(start_date)
        
        while current_date <= end_date:
            payments.append((current_date, amount))
            current_date = self._add_months(current_date, 12)
        
        logger.debug(f"Generated {len(payments)} annual payments")
        return payments
    
    def calculate_period_return(
        self,
        total_value: Decimal,
        annual_return_rate: Decimal,
        frequency: PaymentFrequency
    ) -> Decimal:
        """
        חשב תשואה לתקופה ספציפית.
        
        Args:
            total_value: ערך כולל של הנכס
            annual_return_rate: שיעור תשואה שנתי
            frequency: תדירות תשלום
            
        Returns:
            תשואה לתקופה
        """
        annual_return = total_value * annual_return_rate
        
        if frequency == PaymentFrequency.MONTHLY:
            return annual_return / Decimal('12')
        elif frequency == PaymentFrequency.QUARTERLY:
            return annual_return / Decimal('4')
        elif frequency == PaymentFrequency.ANNUALLY:
            return annual_return
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
    
    def get_payment_interval_months(self, frequency: PaymentFrequency) -> int:
        """
        קבל מרווח תשלום בחודשים.
        
        Args:
            frequency: תדירות תשלום
            
        Returns:
            מספר חודשים בין תשלומים
        """
        if frequency == PaymentFrequency.MONTHLY:
            return 1
        elif frequency == PaymentFrequency.QUARTERLY:
            return 3
        elif frequency == PaymentFrequency.ANNUALLY:
            return 12
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
    
    def is_payment_date(
        self,
        current_date: date,
        start_date: date,
        frequency: PaymentFrequency
    ) -> bool:
        """
        בדוק אם תאריך נוכחי הוא תאריך תשלום.
        
        Args:
            current_date: תאריך לבדיקה
            start_date: תאריך התחלה
            frequency: תדירות תשלום
            
        Returns:
            True אם זה תאריך תשלום
        """
        if frequency == PaymentFrequency.MONTHLY:
            return True  # כל חודש
        
        months_diff = (
            (current_date.year - start_date.year) * 12 +
            (current_date.month - start_date.month)
        )
        
        if frequency == PaymentFrequency.QUARTERLY:
            return months_diff % 3 == 0
        elif frequency == PaymentFrequency.ANNUALLY:
            return months_diff % 12 == 0
        
        return False
    
    def _align_to_first_of_month(self, target_date: date) -> date:
        """
        יישר תאריך לתחילת החודש.
        
        Args:
            target_date: תאריך ליישור
            
        Returns:
            תאריך מיושר ל-1 בחודש
        """
        return date(target_date.year, target_date.month, 1)
    
    def _add_months(self, target_date: date, months: int) -> date:
        """
        הוסף חודשים לתאריך.
        
        Args:
            target_date: תאריך בסיס
            months: מספר חודשים להוספה
            
        Returns:
            תאריך חדש
        """
        return target_date + relativedelta(months=months)
