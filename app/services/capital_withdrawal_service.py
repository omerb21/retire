"""
Capital Withdrawal Service - שירות משיכת כספי הון

מחשב את המס על משיכה חד-פעמית מכספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים),
לפי מדרגות מס הכנסה בשנת המשיכה.

הערה: שירות זה מחשב מס הכנסה בלבד (ללא ביטוח לאומי/בריאות).
"""

from decimal import Decimal
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# מדרגות מס הכנסה לפי שנים
TAX_BRACKETS = {
    2024: [
        (Decimal("81480"), Decimal("0.10")),
        (Decimal("116760"), Decimal("0.14")),
        (Decimal("187440"), Decimal("0.20")),
        (Decimal("401880"), Decimal("0.31")),
        (Decimal("647640"), Decimal("0.35")),
        (None, Decimal("0.47")),
    ],
    2025: [
        (Decimal("84000"), Decimal("0.14")),
        (Decimal("205680"), Decimal("0.20")),
        (Decimal("403680"), Decimal("0.31")),
        (Decimal("655200"), Decimal("0.35")),
        (None, Decimal("0.47")),
    ],
    2026: [
        (Decimal("84000"), Decimal("0.14")),
        (Decimal("205680"), Decimal("0.20")),
        (Decimal("403680"), Decimal("0.31")),
        (Decimal("655200"), Decimal("0.35")),
        (None, Decimal("0.47")),
    ],
}


def get_tax_brackets(year: int) -> list:
    """מחזיר מדרגות מס לשנה נתונה. אם השנה לא קיימת, משתמש ב-2025."""
    return TAX_BRACKETS.get(year, TAX_BRACKETS[2025])


def calculate_tax_on_withdrawal(
    withdrawal_amount: Decimal,
    other_annual_income: Decimal = Decimal("0"),
    tax_year: Optional[int] = None,
) -> Dict[str, Decimal]:
    """
    מחשב מס הכנסה על משיכת כספי הון.

    המס מחושב לפי מדרגות המס השוליות, בהתחשב בהכנסות אחרות באותה שנה.

    Args:
        withdrawal_amount: סכום המשיכה ברוטו
        other_annual_income: הכנסה שנתית אחרת (משכורת, קצבה וכו')
        tax_year: שנת המשיכה

    Returns:
        Dict עם gross, tax, net, effective_rate
    """
    if withdrawal_amount <= 0:
        return {
            "gross": Decimal("0"),
            "tax": Decimal("0"),
            "net": Decimal("0"),
            "effective_rate": Decimal("0"),
        }

    if tax_year is None:
        tax_year = datetime.now().year

    brackets = get_tax_brackets(int(tax_year))

    total_income = other_annual_income + withdrawal_amount
    base_income = other_annual_income

    def calc_tax(income: Decimal) -> Decimal:
        """מחשב מס לפי מדרגות."""
        if income <= 0:
            return Decimal("0")
        tax = Decimal("0")
        prev_limit = Decimal("0")
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
        return tax.quantize(Decimal("1"))

    tax_with_withdrawal = calc_tax(total_income)
    tax_without_withdrawal = calc_tax(base_income)
    marginal_tax = tax_with_withdrawal - tax_without_withdrawal

    effective_rate = (
        (marginal_tax / withdrawal_amount * 100)
        if withdrawal_amount > 0
        else Decimal("0")
    )

    return {
        "gross": withdrawal_amount,
        "tax": marginal_tax,
        "net": withdrawal_amount - marginal_tax,
        "effective_rate": effective_rate.quantize(Decimal("0.1")),
    }


def calculate_capital_withdrawal(
    withdrawal_amount_gross: float,
    withdrawal_year: Optional[int] = None,
    other_annual_income: float = 0.0,
) -> Dict[str, Any]:
    """
    מחשב משיכת כספי הון עם פירוט מלא.

    Args:
        withdrawal_amount_gross: סכום המשיכה ברוטו
        withdrawal_year: שנת המשיכה המתוכננת
        other_annual_income: הכנסה שנתית אחרת (אופציונלי)

    Returns:
        Dict עם כל פרטי החישוב
    """
    withdrawal = Decimal(str(withdrawal_amount_gross))
    other_income = Decimal(str(other_annual_income))

    tax_result = calculate_tax_on_withdrawal(
        withdrawal_amount=withdrawal,
        other_annual_income=other_income,
        tax_year=withdrawal_year,
    )

    # חישוב מדרגת המס השולית
    if withdrawal_year is None:
        withdrawal_year = datetime.now().year

    brackets = get_tax_brackets(int(withdrawal_year))
    total_income = other_income + withdrawal
    marginal_rate = Decimal("0")
    for limit, rate in brackets:
        if limit is None or total_income <= limit:
            marginal_rate = rate
            break

    return {
        "withdrawal_amount_gross": float(withdrawal),
        "withdrawal_year": withdrawal_year,
        "other_annual_income": float(other_income),
        "tax_amount": float(tax_result["tax"]),
        "net_amount": float(tax_result["net"]),
        "effective_tax_rate": float(tax_result["effective_rate"]),
        "marginal_tax_rate": float(marginal_rate * 100),
        "tax_brackets_used": withdrawal_year,
    }


class CapitalWithdrawalService:
    """שירות משיכת כספי הון"""

    def __init__(self, db=None, client_id: Optional[int] = None):
        self.db = db
        self.client_id = client_id

    def calculate(
        self,
        withdrawal_amount_gross: float,
        withdrawal_year: Optional[int] = None,
        other_annual_income: float = 0.0,
    ) -> Dict[str, Any]:
        """
        מחשב משיכת כספי הון.

        Args:
            withdrawal_amount_gross: סכום המשיכה ברוטו
            withdrawal_year: שנת המשיכה
            other_annual_income: הכנסה שנתית אחרת

        Returns:
            Dict עם פרטי החישוב
        """
        return calculate_capital_withdrawal(
            withdrawal_amount_gross=withdrawal_amount_gross,
            withdrawal_year=withdrawal_year,
            other_annual_income=other_annual_income,
        )
