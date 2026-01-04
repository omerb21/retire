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
         benefit_percentage = (tax_benefit / immediate_tax * 100) if immediate_tax > 0 else 0
         
         # חישוב שיעורי מס אפקטיביים
         immediate_effective_rate = (immediate_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
         spread_effective_rate = (spread_total_tax / float(gross_amount) * 100) if gross_amount > 0 else 0
         
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
             explanation_lines.append(f"**💡 המלצה:** פריסה ל-{spread_years} שנים חוסכת {tax_benefit:,.0f} ₪ במס.")
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


     def get_tax_projection(
         self,
         monthly_pension: Optional[float] = None,
         additional_income: Optional[float] = None,
     ) -> Dict[str, Any]:
         """
         מחשב הערכת מס על הכנסה בפרישה.
         אם לא מסופקים פרמטרים, משתמש בנתונים מהתרחישים הקיימים.
         """
         from app.models.additional_income import AdditionalIncome
         from app.models.fixation_result import FixationResult
         from app.providers.tax_params import InMemoryTaxParamsProvider
         from app.services.additional_income_service import AdditionalIncomeService

         client = self.client
         if not client:
             return {
                 "success": False,
                 "tool_name": "GET_TAX_PROJECTION",
                 "result": {},
                 "explanation": "לא נמצא לקוח.",
             }

         # אם לא סופקה קצבה, נסה לקחת מהתרחישים
         if monthly_pension is None:
             scenarios = self.db.query(Scenario).filter(
                 Scenario.client_id == self.client_id
             ).order_by(Scenario.created_at.desc()).first()

             if scenarios and scenarios.summary_results:
                 try:
                     summary = json.loads(scenarios.summary_results)
                     monthly_pension = summary.get("total_pension_monthly", 0)
                 except Exception:
                     monthly_pension = 0
             else:
                 monthly_pension = 0

         # Fallback: if still missing, use existing pensions (DB) as a conservative default.
         if not monthly_pension:
             try:
                 pension_funds = (
                     self.db.query(PensionFund)
                     .filter(PensionFund.client_id == self.client_id)
                     .all()
                 )
                 monthly_pension = sum(float(pf.pension_amount or 0) for pf in pension_funds)
             except Exception:
                 monthly_pension = 0

         if additional_income is None:
             additional_income = 0

         # Threshold for monthly pension gross – stability guardrail.
         gross_monthly_pension = float(monthly_pension or 0)
         if gross_monthly_pension < 1000:
             raise ValueError(
                 "TAX_TOOL_ERROR: הקצבה החודשית נמוכה מ-1,000 ₪, לא ניתן לבצע הערכת מס אמינה."
             )

         # Collect additional incomes from DB (deterministically).
         additional_income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
         additional_rows = (
             self.db.query(AdditionalIncome)
             .filter(AdditionalIncome.client_id == self.client_id)
             .all()
         )

         annual_salary_income = 0.0
         annual_business_income = 0.0
         annual_rental_income = 0.0
         annual_interest_income = 0.0
         annual_dividend_income = 0.0
         annual_other_income = 0.0

         fixed_rate_income_monthly = 0.0
         fixed_rate_tax_annual = 0.0

         for inc in additional_rows:
             try:
                 if inc.start_date and inc.start_date > date.today():
                     continue
                 if inc.end_date and inc.end_date < date.today():
                     continue
             except Exception:
                 pass

             try:
                 monthly_val = float(additional_income_service.calculate_monthly_amount(inc) or 0)
             except Exception:
                 try:
                     monthly_val = float(getattr(inc, "amount", 0) or 0)
                 except Exception:
                     monthly_val = 0.0

             if monthly_val <= 0:
                 continue

             tax_treatment = str(getattr(inc, "tax_treatment", "") or "").strip().lower()
             if tax_treatment == "exempt":
                 continue

             if tax_treatment == "fixed_rate":
                 fixed_rate_income_monthly += monthly_val
                 try:
                     tax_rate = float(getattr(inc, "tax_rate", 0) or 0)
                 except Exception:
                     tax_rate = 0.0
                 fixed_rate_tax_annual += (monthly_val * 12) * (tax_rate / 100.0)
                 continue

             annual_val = monthly_val * 12
             source_type = str(getattr(inc, "source_type", "") or "").strip().lower()
             if source_type == "salary":
                 annual_salary_income += annual_val
             elif source_type == "business":
                 annual_business_income += annual_val
             elif source_type == "rental":
                 annual_rental_income += annual_val
             elif source_type == "interest":
                 annual_interest_income += annual_val
             elif source_type == "dividends":
                 annual_dividend_income += annual_val
             else:
                 annual_other_income += annual_val

         # Tool arg can add an extra taxable "other" income not in DB.
         try:
             manual_additional_monthly = float(additional_income or 0)
         except Exception:
             manual_additional_monthly = 0.0
         if manual_additional_monthly > 0:
             annual_other_income += manual_additional_monthly * 12

         current_year = date.today().year

         fixation = (
             self.db.query(FixationResult)
             .filter(FixationResult.client_id == self.client_id)
             .order_by(FixationResult.created_at.desc())
             .first()
         )
         exempt_pension_pct = 0.0
         if fixation and fixation.raw_result:
             try:
                 fixation_data = (
                     fixation.raw_result
                     if isinstance(fixation.raw_result, dict)
                     else json.loads(fixation.raw_result)
                 )
                 exempt_pension_pct = float(
                     (fixation_data.get("exemption_summary", {}) or {}).get(
                         "exempt_pension_percentage", 0
                     )
                     or 0
                 )
             except Exception:
                 exempt_pension_pct = 0.0

         exempt_pension_amount_monthly = 0.0
         if exempt_pension_pct > 0:
             try:
                 exempt_pension_amount_monthly = float(get_monthly_cap(current_year)) * float(
                     exempt_pension_pct
                 )
             except Exception:
                 exempt_pension_amount_monthly = 0.0

         personal_details = PersonalDetails(
             birth_date=getattr(client, "birth_date", None),
             marital_status=getattr(client, "marital_status", "single") or "single",
             num_children=int(getattr(client, "num_children", 0) or 0),
             is_new_immigrant=bool(getattr(client, "is_new_immigrant", False)),
             is_veteran=bool(getattr(client, "is_veteran", False)),
             is_disabled=bool(getattr(client, "is_disabled", False)),
             disability_percentage=getattr(client, "disability_percentage", None),
             is_student=bool(getattr(client, "is_student", False)),
             reserve_duty_days=int(getattr(client, "reserve_duty_days", 0) or 0),
         )

         tax_input = TaxCalculationInput(
             tax_year=current_year,
             personal_details=personal_details,
             salary_income=annual_salary_income,
             pension_income=gross_monthly_pension * 12,
             rental_income=annual_rental_income,
             business_income=annual_business_income,
             interest_income=annual_interest_income,
             dividend_income=annual_dividend_income,
             other_income=annual_other_income,
             pension_contributions=float(getattr(client, "pension_contributions", 0) or 0),
             study_fund_contributions=float(getattr(client, "study_fund_contributions", 0) or 0),
             insurance_premiums=float(getattr(client, "insurance_premiums", 0) or 0),
             charitable_donations=float(getattr(client, "charitable_donations", 0) or 0),
             exempt_pension_amount=exempt_pension_amount_monthly,
             pension_months_in_year=12,
         )

         calculator = TaxCalculator(tax_year=current_year)
         tax_result = calculator.calculate_comprehensive_tax(tax_input)

         annual_tax = float(tax_result.net_tax)
         monthly_tax = annual_tax / 12

         # Explanations must be based on system-calculated outputs only.
         tax_explanation_parts: list[str] = []
         tax_explanation_parts.append("💵 **הערכת מס בפרישה (דטרמיניסטי - מחשבון מערכת)**")
         tax_explanation_parts.append("")
         tax_explanation_parts.append("**📊 הכנסות שנלקחו בחשבון:**")
         tax_explanation_parts.append(f"  • קצבה חודשית: {gross_monthly_pension:,.0f} ₪")

         taxable_additional_monthly = (
             annual_salary_income
             + annual_business_income
             + annual_rental_income
             + annual_interest_income
             + annual_dividend_income
             + annual_other_income
         ) / 12
         if taxable_additional_monthly > 0:
             tax_explanation_parts.append(
                 f"  • הכנסות נוספות (חייבות/מיוחדות): {taxable_additional_monthly:,.0f} ₪/חודש"
             )
         if fixed_rate_income_monthly > 0:
             tax_explanation_parts.append(
                 f"  • הכנסות נוספות במס קבוע (לא נכלל בחישוב מס ההכנסה): {fixed_rate_income_monthly:,.0f} ₪/חודש"
             )

         tax_explanation_parts.append("")
         tax_explanation_parts.append("**💰 מס לפי מחשבון המערכת:**")
         tax_explanation_parts.append(f"  • מס שנתי: {annual_tax:,.0f} ₪")
         tax_explanation_parts.append(f"  • מס חודשי: {monthly_tax:,.0f} ₪")
         tax_explanation_parts.append(
             f"  • שיעור מס אפקטיבי: {float(tax_result.effective_tax_rate):.1f}%"
         )

         if exempt_pension_pct > 0:
             tax_explanation_parts.append("")
             tax_explanation_parts.append(
                 f"✅ **פטור קצבה מקיבוע זכויות**: {exempt_pension_pct*100:.1f}% מהתקרה המזכה (תורגם לסכום פטור חודשי לפי שנת {current_year})"
             )

         return {
             "success": True,
             "tool_name": "GET_TAX_PROJECTION",
             "result": {
                 "monthly_pension": gross_monthly_pension,
                 "additional_income": float(additional_income or 0),
                 "portfolio_additional_income_monthly": taxable_additional_monthly,
                 "fixed_rate_income_monthly": fixed_rate_income_monthly,
                 "fixed_rate_tax_annual": fixed_rate_tax_annual,
                 "total_annual_income": float(tax_result.total_income),
                 "annual_tax": annual_tax,
                 "monthly_tax": monthly_tax,
                 "effective_rate": float(tax_result.effective_tax_rate),
                 "exempt_pension_percentage": exempt_pension_pct,
                 "exempt_pension_amount_monthly": exempt_pension_amount_monthly,
                 "tax_breakdown": _to_jsonable(getattr(tax_result, "tax_breakdown", [])),
                 "income_breakdown": _to_jsonable(getattr(tax_result, "income_breakdown", [])),
             },
             "explanation": "\n".join(tax_explanation_parts),
         }


     def calculate_required_gross_withdrawal(
         self,
         desired_net_income: float,
         guaranteed_pension: float,
         retirement_date: Optional[str] = None,
     ) -> Dict[str, Any]:
         """
         מחשב את סכום הברוטו החודשי שצריך למשוך מההון כך שלאחר מס,
         ההכנסה החודשית נטו (קצבה מובטחת + משיכה) תגיע ליעד המבוקש.

         משתמש באותן מדרגות מס ופטור קצבה כמו GET_TAX_PROJECTION.
         """
         from app.services.tax_data.tax_brackets import TaxBracketsService
         from app.models.fixation_result import FixationResult
         from datetime import datetime

         client = self.client
         if not client:
             return {
                 "success": False,
                 "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                 "result": {},
                 "explanation": "לא נמצא לקוח.",
             }

         # אם לא סופקה קצבה, נסה לקחת מהתרחישים
         if guaranteed_pension is None:
             scenarios = self.db.query(Scenario).filter(
                 Scenario.client_id == self.client_id
             ).order_by(Scenario.created_at.desc()).first()

             if scenarios and scenarios.summary_results:
                 try:
                     summary = json.loads(scenarios.summary_results)
                     guaranteed_pension = summary.get("total_pension_monthly", 0)
                 except Exception:
                     guaranteed_pension = 0
             else:
                 guaranteed_pension = 0

         # Fallback: if still missing, use existing pensions (DB) as a conservative default.
         if not guaranteed_pension:
             try:
                 pension_funds = (
                     self.db.query(PensionFund)
                     .filter(PensionFund.client_id == self.client_id)
                     .all()
                 )
                 guaranteed_pension = sum(float(pf.pension_amount or 0) for pf in pension_funds)
             except Exception:
                 guaranteed_pension = 0

         if retirement_date:
             try:
                 retirement_date_obj = parse_date_flexible(retirement_date)
             except ValueError:
                 return {
                     "success": False,
                     "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                     "result": {},
                     "explanation": f"תאריך לא תקין: {retirement_date}. יש להשתמש בפורמט YYYY-MM-DD.",
                 }
         else:
             retirement_date_obj = date.today()

         # Threshold for monthly pension gross – stability guardrail.
         gross_monthly_pension = float(guaranteed_pension or 0)
         if gross_monthly_pension < 1000:
             raise ValueError(
                 "TAX_TOOL_ERROR: הקצבה החודשית נמוכה מ-1,000 ₪, לא ניתן לבצע הערכת מס אמינה."
             )

         # Collect additional incomes from DB (deterministically).
         additional_income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
         additional_rows = (
             self.db.query(AdditionalIncome)
             .filter(AdditionalIncome.client_id == self.client_id)
             .all()
         )

         annual_salary_income = 0.0
         annual_business_income = 0.0
         annual_rental_income = 0.0
         annual_interest_income = 0.0
         annual_dividend_income = 0.0
         annual_other_income = 0.0

         fixed_rate_income_monthly = 0.0
         fixed_rate_tax_annual = 0.0

         for inc in additional_rows:
             try:
                 if inc.start_date and inc.start_date > date.today():
                     continue
                 if inc.end_date and inc.end_date < date.today():
                     continue
             except Exception:
                 pass

             try:
                 monthly_val = float(additional_income_service.calculate_monthly_amount(inc) or 0)
             except Exception:
                 try:
                     monthly_val = float(getattr(inc, "amount", 0) or 0)
                 except Exception:
                     monthly_val = 0.0

             if monthly_val <= 0:
                 continue

             tax_treatment = str(getattr(inc, "tax_treatment", "") or "").strip().lower()
             if tax_treatment == "exempt":
                 continue

             if tax_treatment == "fixed_rate":
                 fixed_rate_income_monthly += monthly_val
                 try:
                     tax_rate = float(getattr(inc, "tax_rate", 0) or 0)
                 except Exception:
                     tax_rate = 0.0
                 fixed_rate_tax_annual += (monthly_val * 12) * (tax_rate / 100.0)
                 continue

             annual_val = monthly_val * 12
             source_type = str(getattr(inc, "source_type", "") or "").strip().lower()
             if source_type == "salary":
                 annual_salary_income += annual_val
             elif source_type == "business":
                 annual_business_income += annual_val
             elif source_type == "rental":
                 annual_rental_income += annual_val
             elif source_type == "interest":
                 annual_interest_income += annual_val
             elif source_type == "dividends":
                 annual_dividend_income += annual_val
             else:
                 annual_other_income += annual_val

         # Tool arg can add an extra taxable "other" income not in DB.
         try:
             manual_additional_monthly = float(desired_net_income or 0)
         except Exception:
             manual_additional_monthly = 0.0
         if manual_additional_monthly > 0:
             annual_other_income += manual_additional_monthly * 12

         current_year = retirement_date_obj.year

         fixation = (
             self.db.query(FixationResult)
             .filter(FixationResult.client_id == self.client_id)
             .order_by(FixationResult.created_at.desc())
             .first()
         )
         exempt_pension_pct = 0.0
         if fixation and fixation.raw_result:
             try:
                 fixation_data = (
                     fixation.raw_result
                     if isinstance(fixation.raw_result, dict)
                     else json.loads(fixation.raw_result)
                 )
                 exempt_pension_pct = float(
                     (fixation_data.get("exemption_summary", {}) or {}).get(
                         "exempt_pension_percentage", 0
                     )
                     or 0
                 )
             except Exception:
                 exempt_pension_pct = 0.0

         exempt_pension_amount_monthly = 0.0
         if exempt_pension_pct > 0:
             try:
                 exempt_pension_amount_monthly = float(get_monthly_cap(current_year)) * float(
                     exempt_pension_pct
                 )
             except Exception:
                 exempt_pension_amount_monthly = 0.0

         personal_details = PersonalDetails(
             birth_date=getattr(client, "birth_date", None),
             marital_status=getattr(client, "marital_status", "single") or "single",
             num_children=int(getattr(client, "num_children", 0) or 0),
             is_new_immigrant=bool(getattr(client, "is_new_immigrant", False)),
             is_veteran=bool(getattr(client, "is_veteran", False)),
             is_disabled=bool(getattr(client, "is_disabled", False)),
             disability_percentage=getattr(client, "disability_percentage", None),
             is_student=bool(getattr(client, "is_student", False)),
             reserve_duty_days=int(getattr(client, "reserve_duty_days", 0) or 0),
         )

         tax_input = TaxCalculationInput(
             tax_year=current_year,
             personal_details=personal_details,
             salary_income=annual_salary_income,
             pension_income=gross_monthly_pension * 12,
             rental_income=annual_rental_income,
             business_income=annual_business_income,
             interest_income=annual_interest_income,
             dividend_income=annual_dividend_income,
             other_income=annual_other_income,
             pension_contributions=float(getattr(client, "pension_contributions", 0) or 0),
             study_fund_contributions=float(getattr(client, "study_fund_contributions", 0) or 0),
             insurance_premiums=float(getattr(client, "insurance_premiums", 0) or 0),
             charitable_donations=float(getattr(client, "charitable_donations", 0) or 0),
             exempt_pension_amount=exempt_pension_amount_monthly,
             pension_months_in_year=12,
         )

         calculator = TaxCalculator(tax_year=current_year)
         tax_result = calculator.calculate_comprehensive_tax(tax_input)

         annual_tax = float(tax_result.net_tax)
         monthly_tax = annual_tax / 12

         # Explanations must be based on system-calculated outputs only.
         tax_explanation_parts: list[str] = []
         tax_explanation_parts.append("💵 **הערכת מס בפרישה (דטרמיניסטי - מחשבון מערכת)**")
         tax_explanation_parts.append("")
         tax_explanation_parts.append("**📊 הכנסות שנלקחו בחשבון:**")
         tax_explanation_parts.append(f"  • קצבה חודשית: {gross_monthly_pension:,.0f} ₪")

         taxable_additional_monthly = (
             annual_salary_income
             + annual_business_income
             + annual_rental_income
             + annual_interest_income
             + annual_dividend_income
             + annual_other_income
         ) / 12
         if taxable_additional_monthly > 0:
             tax_explanation_parts.append(
                 f"  • הכנסות נוספות (חייבות/מיוחדות): {taxable_additional_monthly:,.0f} ₪/חודש"
             )
         if fixed_rate_income_monthly > 0:
             tax_explanation_parts.append(
                 f"  • הכנסות נוספות במס קבוע (לא נכלל בחישוב מס ההכנסה): {fixed_rate_income_monthly:,.0f} ₪/חודש"
             )

         tax_explanation_parts.append("")
         tax_explanation_parts.append("**💰 מס לפי מחשבון המערכת:**")
         tax_explanation_parts.append(f"  • מס שנתי: {annual_tax:,.0f} ₪")
         tax_explanation_parts.append(f"  • מס חודשי: {monthly_tax:,.0f} ₪")
         tax_explanation_parts.append(
             f"  • שיעור מס אפקטיבי: {float(tax_result.effective_tax_rate):.1f}%"
         )

         if exempt_pension_pct > 0:
             tax_explanation_parts.append("")
             tax_explanation_parts.append(
                 f"✅ **פטור קצבה מקיבוע זכויות**: {exempt_pension_pct*100:.1f}% מהתקרה המזכה (תורגם לסכום פטור חודשי לפי שנת {current_year})"
             )

         return {
             "success": True,
             "tool_name": "GET_TAX_PROJECTION",
             "result": {
                 "monthly_pension": gross_monthly_pension,
                 "additional_income": float(desired_net_income or 0),
                 "portfolio_additional_income_monthly": taxable_additional_monthly,
                 "fixed_rate_income_monthly": fixed_rate_income_monthly,
                 "fixed_rate_tax_annual": fixed_rate_tax_annual,
                 "total_annual_income": float(tax_result.total_income),
                 "annual_tax": annual_tax,
                 "monthly_tax": monthly_tax,
                 "effective_rate": float(tax_result.effective_tax_rate),
                 "exempt_pension_percentage": exempt_pension_pct,
                 "exempt_pension_amount_monthly": exempt_pension_amount_monthly,
                 "tax_breakdown": _to_jsonable(getattr(tax_result, "tax_breakdown", [])),
                 "income_breakdown": _to_jsonable(getattr(tax_result, "income_breakdown", [])),
             },
             "explanation": "\n".join(tax_explanation_parts),
         }
