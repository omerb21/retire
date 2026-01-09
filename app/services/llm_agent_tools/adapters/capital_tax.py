import logging
from datetime import date
from typing import Any, Dict, Optional

from app.services.capital_withdrawal_service import CapitalWithdrawalService

logger = logging.getLogger("app.llm_agent_tools")


def calculate_capital_withdrawal_tax(
    self,
    withdrawal_amount_gross: float,
    withdrawal_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    מחשב מס על משיכת כספי הון (קופת גמל, קרן השתלמות, תגמולים נזילים).

    Args:
        withdrawal_amount_gross: סכום המשיכה ברוטו
        withdrawal_year: שנת המשיכה המתוכננת

    Returns:
        Dict עם סכום המס, הסכום נטו, ושיעור המס האפקטיבי
    """
    client = self.client
    if not client:
        return {
            "success": False,
            "tool_name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
            "result": {},
            "explanation": "לא נמצא לקוח עם המזהה שסופק.",
        }

    # הכנסה שנתית אחרת (אם יש)
    other_annual_income = 0.0
    if client.annual_salary:
        other_annual_income = float(client.annual_salary)

    if withdrawal_year is None:
        withdrawal_year = date.today().year

    # ביצוע חישוב המס
    withdrawal_service = CapitalWithdrawalService(self.db, self.client_id)
    result = withdrawal_service.calculate(
        withdrawal_amount_gross=withdrawal_amount_gross,
        withdrawal_year=withdrawal_year,
        other_annual_income=other_annual_income,
    )

    # בניית הסבר מפורט
    explanation_lines = [
        f"💰 **חישוב מס על משיכת כספי הון**",
        f"",
        f"**פרטי המשיכה:**",
        f"  • סכום המשיכה ברוטו: {result['withdrawal_amount_gross']:,.0f} ₪",
        f"  • שנת המשיכה: {result['withdrawal_year']}",
    ]

    if other_annual_income > 0:
        explanation_lines.append(f"  • הכנסה שנתית אחרת: {other_annual_income:,.0f} ₪")

    explanation_lines.extend(
        [
            f"",
            f"**חישוב המס:**",
            f"  • מס הכנסה: {result['tax_amount']:,.0f} ₪",
            f"  • שיעור מס אפקטיבי: {result['effective_tax_rate']:.1f}%",
            f"  • מדרגת מס שולית: {result['marginal_tax_rate']:.0f}%",
            f"",
            f"**סכום נטו:**",
            f"  • **תקבל לידיים: {result['net_amount']:,.0f} ₪**",
            f"",
            f"**💡 שים לב:**",
            f"  • החישוב מתייחס למס הכנסה בלבד (ללא ביטוח לאומי/בריאות)",
            f"  • המס מחושב לפי מדרגות המס לשנת {result['withdrawal_year']}",
        ]
    )

    if other_annual_income > 0:
        explanation_lines.append(f"  • המס מחושב בהתחשב בהכנסה השנתית הנוספת שלך")

    return {
        "success": True,
        "tool_name": "CALCULATE_CAPITAL_WITHDRAWAL_TAX",
        "result": {
            "withdrawal_amount_gross": result["withdrawal_amount_gross"],
            "withdrawal_year": result["withdrawal_year"],
            "tax_amount": result["tax_amount"],
            "net_amount": result["net_amount"],
            "effective_tax_rate": result["effective_tax_rate"],
            "marginal_tax_rate": result["marginal_tax_rate"],
        },
        "explanation": "\n".join(explanation_lines),
    }
