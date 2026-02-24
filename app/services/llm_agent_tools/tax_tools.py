import logging
from datetime import date
from typing import Any, Dict, Optional
from app.schemas.tax_schemas import PersonalDetails, TaxCalculationInput
from app.services.tax_calculator import TaxCalculator
from app.services.llm_agent_tools.utils import _to_jsonable

logger = logging.getLogger("app.llm_agent_tools")


class TaxToolsMixin:
    def calculate_tax_spread_benefit(
        self,
        gross_amount: float,
        spread_years: int,
    ) -> Dict[str, Any]:
        """
        מחשב את הטבת המס בפריסה על מספר שנים.
        משווה בין משיכה מיידית (מס מלא) לבין פריסת מס על מספר שנים.

        Args:
            gross_amount: סכום ברוטו חייב במס
            spread_years: מספר שנות פריסה (1-6)

        Returns:
            Dict עם השוואת מס מיידי מול פריסה והטבת המס
        """
        from decimal import Decimal
        from app.services.capital_asset.tax_calculator import TaxCalculator

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # וידוא שנות פריסה תקינות
        if spread_years < 1 or spread_years > 6:
            return {
                "success": False,
                "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
                "result": {},
                "explanation": f"מספר שנות פריסה לא תקין ({spread_years}). יש לבחור בין 1 ל-6 שנים.",
            }

        # יצירת מחשבון מס
        tax_calculator = TaxCalculator()

        # חישוב מס מיידי (ללא פריסה)
        from app.models.capital_asset import TaxTreatment

        immediate_result = tax_calculator.calculate(
            gross_amount=Decimal(str(gross_amount)),
            tax_treatment=TaxTreatment.TAXABLE,
        )

        # חישוב מס עם פריסה
        spread_result = tax_calculator.calculate(
            gross_amount=Decimal(str(gross_amount)),
            tax_treatment=TaxTreatment.TAX_SPREAD,
            spread_years=spread_years,
        )

        # חישוב מס מיידי לפי מדרגות (כי TAXABLE מחזיר 0)
        from app.services.tax_data.tax_brackets import TaxBracketsService

        current_year = date.today().year
        tax_brackets = TaxBracketsService.get_tax_brackets(current_year)

        # חישוב מס מיידי לפי מדרגות
        immediate_tax = 0.0
        remaining = float(gross_amount)
        for bracket in tax_brackets:
            if remaining <= 0:
                break
            bracket_min = bracket["min_income"]
            bracket_max = bracket["max_income"]
            rate = bracket["rate"]
            taxable_in_bracket = min(remaining, bracket_max - bracket_min + 1)
            if taxable_in_bracket > 0:
                immediate_tax += taxable_in_bracket * rate
                remaining -= taxable_in_bracket

        # חישוב מס עם פריסה לפי מדרגות
        annual_portion = float(gross_amount) / spread_years
        annual_tax = 0.0
        remaining = annual_portion
        for bracket in tax_brackets:
            if remaining <= 0:
                break
            bracket_min = bracket["min_income"]
            bracket_max = bracket["max_income"]
            rate = bracket["rate"]
            taxable_in_bracket = min(remaining, bracket_max - bracket_min + 1)
            if taxable_in_bracket > 0:
                annual_tax += taxable_in_bracket * rate
                remaining -= taxable_in_bracket

        spread_total_tax = annual_tax * spread_years

        # חישוב הטבת המס
        tax_benefit = immediate_tax - spread_total_tax
        benefit_percentage = (
            (tax_benefit / immediate_tax * 100) if immediate_tax > 0 else 0
        )

        # חישוב שיעורי מס אפקטיביים
        immediate_effective_rate = (
            (immediate_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
        )
        spread_effective_rate = (
            (spread_total_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
        )

        # בניית הסבר מפורט
        explanation_lines = [
            f"📊 **ניתוח פריסת מס**",
            f"",
            f"**פרטי הסכום:**",
            f"  • סכום ברוטו חייב במס: {gross_amount:,.0f} ₪",
            f"  • שנות פריסה: {spread_years}",
            f"  • חלק שנתי: {annual_portion:,.0f} ₪",
            f"",
            f"**השוואת מס:**",
            f"",
            f"| אופציה | מס כולל | שיעור אפקטיבי | נטו |",
            f"|--------|---------|---------------|-----|",
            f"| משיכה מיידית | {immediate_tax:,.0f} ₪ | {immediate_effective_rate:.1f}% | {gross_amount - immediate_tax:,.0f} ₪ |",
            f"| פריסה ל-{spread_years} שנים | {spread_total_tax:,.0f} ₪ | {spread_effective_rate:.1f}% | {gross_amount - spread_total_tax:,.0f} ₪ |",
            f"",
            f"**💰 הטבת המס בפריסה:**",
            f"  • חיסכון במס: **{tax_benefit:,.0f} ₪** ({benefit_percentage:.1f}%)",
            f"  • תוספת נטו: **{tax_benefit:,.0f} ₪**",
            f"",
        ]

        if tax_benefit > 0:
            explanation_lines.append(
                f"**💡 המלצה:** פריסה ל-{spread_years} שנים חוסכת {tax_benefit:,.0f} ₪ במס."
            )
        else:
            explanation_lines.append(f"**💡 הערה:** אין הטבה משמעותית בפריסה במקרה זה.")

        return {
            "success": True,
            "tool_name": "CALCULATE_TAX_SPREAD_BENEFIT",
            "result": {
                "gross_amount": gross_amount,
                "spread_years": spread_years,
                "annual_portion": annual_portion,
                "immediate_tax": immediate_tax,
                "immediate_net": gross_amount - immediate_tax,
                "immediate_effective_rate": immediate_effective_rate,
                "spread_total_tax": spread_total_tax,
                "spread_net": gross_amount - spread_total_tax,
                "spread_effective_rate": spread_effective_rate,
                "annual_tax": annual_tax,
                "tax_benefit": tax_benefit,
                "benefit_percentage": benefit_percentage,
            },
            "explanation": "\n".join(explanation_lines),
        }
