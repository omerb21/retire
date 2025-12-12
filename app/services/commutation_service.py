"""
Commutation Service - שירות היוון קצבה

מחשב את סכום ההון שניתן לקבל בתמורה לוויתור על חלק מהקצבה החודשית,
כולל חישוב המס על סכום ההיוון.

היוון קצבה = המרת זרם תשלומים עתידי (קצבה חודשית) לסכום חד-פעמי היום.
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# מדרגות מס הכנסה 2025
TAX_BRACKETS_2025 = [
    (Decimal('84000'), Decimal('0.14')),
    (Decimal('205680'), Decimal('0.20')),
    (Decimal('403680'), Decimal('0.31')),
    (Decimal('655200'), Decimal('0.35')),
    (None, Decimal('0.47')),
]


def calculate_tax_on_lump_sum(
    lump_sum: Decimal,
    other_annual_income: Decimal = Decimal('0'),
    tax_year: int = 2025
) -> Dict[str, Decimal]:
    """
    מחשב מס הכנסה על סכום חד-פעמי (היוון).
    
    לפי פקודת מס הכנסה, היוון קצבה חייב במס כהכנסה רגילה בשנת הקבלה.
    המס מחושב לפי מדרגות המס השוליות.
    
    Args:
        lump_sum: סכום ההיוון ברוטו
        other_annual_income: הכנסה שנתית אחרת (לחישוב מדרגות)
        tax_year: שנת המס
        
    Returns:
        Dict עם gross, tax, net
    """
    brackets = TAX_BRACKETS_2025
    
    total_income = other_annual_income + lump_sum
    base_income = other_annual_income
    
    def calc_tax(income: Decimal) -> Decimal:
        if income <= 0:
            return Decimal('0')
        tax = Decimal('0')
        prev_limit = Decimal('0')
        for limit, rate in brackets:
            if limit is None:
                tax += (income - prev_limit) * rate
                break
            elif income <= limit:
                tax += (income - prev_limit) * rate
                break
            else:
                tax += (limit - prev_limit) * rate
                prev_limit = limit
        return tax.quantize(Decimal('1'))
    
    tax_with_lump_sum = calc_tax(total_income)
    tax_without_lump_sum = calc_tax(base_income)
    marginal_tax = tax_with_lump_sum - tax_without_lump_sum
    
    return {
        'gross': lump_sum,
        'tax': marginal_tax,
        'net': lump_sum - marginal_tax,
        'effective_rate': (marginal_tax / lump_sum * 100) if lump_sum > 0 else Decimal('0'),
    }


def calculate_commutation(
    monthly_pension_reduction: Decimal,
    annuity_factor: Decimal,
    client_age: int,
    retirement_age: int,
    gender: str = 'זכר',
    other_annual_income: Decimal = Decimal('0'),
) -> Dict[str, Any]:
    """
    מחשב היוון קצבה - המרת קצבה חודשית לסכום חד-פעמי.
    
    הנוסחה הבסיסית:
    סכום היוון = קצבה חודשית × מקדם קצבה
    
    כלומר, אם הלקוח מוותר על X ש"ח בחודש מהקצבה,
    הוא יקבל X × מקדם_קצבה כסכום חד-פעמי.
    
    Args:
        monthly_pension_reduction: הסכום החודשי שהלקוח מוותר עליו (ברוטו)
        annuity_factor: מקדם הקצבה (למשל 200 = כל שקל קצבה שווה 200 ש"ח הון)
        client_age: גיל הלקוח הנוכחי
        retirement_age: גיל הפרישה המתוכנן
        gender: מגדר הלקוח
        other_annual_income: הכנסה שנתית אחרת (לחישוב מדרגות מס)
        
    Returns:
        Dict עם כל פרטי ההיוון
    """
    if monthly_pension_reduction <= 0:
        return {
            'success': False,
            'error': 'סכום ההפחתה החודשית חייב להיות חיובי',
        }
    
    if annuity_factor <= 0:
        annuity_factor = Decimal('200')  # ברירת מחדל
    
    # חישוב סכום ההיוון ברוטו
    lump_sum_gross = monthly_pension_reduction * annuity_factor
    
    # חישוב המס על ההיוון
    tax_result = calculate_tax_on_lump_sum(
        lump_sum=lump_sum_gross,
        other_annual_income=other_annual_income,
    )
    
    # חישוב ערך נוכחי של הקצבה שהלקוח מוותר עליה
    # (לצורך השוואה - כמה שווה הקצבה לאורך זמן)
    years_of_pension = 30  # הנחה: 30 שנות קצבה
    annual_pension_lost = monthly_pension_reduction * 12
    total_pension_lost = annual_pension_lost * years_of_pension
    
    # NPV של הקצבה שהלקוח מוותר עליה (בהנחת ריבית 3%)
    discount_rate = Decimal('0.03')
    npv_pension_lost = Decimal('0')
    for year in range(1, years_of_pension + 1):
        npv_pension_lost += annual_pension_lost / ((1 + discount_rate) ** year)
    npv_pension_lost = npv_pension_lost.quantize(Decimal('1'))
    
    return {
        'success': True,
        'monthly_pension_reduction': float(monthly_pension_reduction),
        'annuity_factor': float(annuity_factor),
        'lump_sum_gross': float(lump_sum_gross),
        'tax_on_lump_sum': float(tax_result['tax']),
        'lump_sum_net': float(tax_result['net']),
        'effective_tax_rate': float(tax_result['effective_rate']),
        'annual_pension_lost': float(annual_pension_lost),
        'total_pension_lost_30_years': float(total_pension_lost),
        'npv_pension_lost': float(npv_pension_lost),
        'comparison': {
            'lump_sum_net': float(tax_result['net']),
            'npv_pension_lost': float(npv_pension_lost),
            'difference': float(tax_result['net'] - npv_pension_lost),
            'recommendation': 'lump_sum' if tax_result['net'] > npv_pension_lost else 'pension',
        },
    }


class CommutationService:
    """שירות היוון קצבה"""
    
    def __init__(self, db=None, client_id: Optional[int] = None):
        self.db = db
        self.client_id = client_id
    
    def calculate(
        self,
        monthly_pension_reduction: float,
        annuity_factor: float = 200.0,
        client_age: int = 67,
        retirement_age: int = 67,
        gender: str = 'זכר',
        other_annual_income: float = 0.0,
    ) -> Dict[str, Any]:
        """
        מחשב היוון קצבה.
        
        Args:
            monthly_pension_reduction: הסכום החודשי להפחתה מהקצבה
            annuity_factor: מקדם הקצבה
            client_age: גיל הלקוח
            retirement_age: גיל הפרישה
            gender: מגדר
            other_annual_income: הכנסה שנתית אחרת
            
        Returns:
            Dict עם תוצאות ההיוון
        """
        return calculate_commutation(
            monthly_pension_reduction=Decimal(str(monthly_pension_reduction)),
            annuity_factor=Decimal(str(annuity_factor)),
            client_age=client_age,
            retirement_age=retirement_age,
            gender=gender,
            other_annual_income=Decimal(str(other_annual_income)),
        )
