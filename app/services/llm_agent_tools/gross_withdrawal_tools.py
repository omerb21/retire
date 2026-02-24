import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("app.llm_agent_tools")


class GrossWithdrawalToolsMixin:
    def calculate_required_gross_withdrawal(
        self,
        desired_net_income: float,
        guaranteed_pension: float,
        retirement_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        מחשב את סכום הברוטו החודשי שצריך למשוך מההון כך שלאחר מס,
        ההכנסה החודשית נטו (קצבה מובטחת + משיכה) תגיע ליעד המבוקש.

        משתמש באותן מדרגות מס ופטור קצבה כמו get_tax_projection.
        """
        import json
        from datetime import date

        from app.models.additional_income import AdditionalIncome
        from app.models.fixation_result import FixationResult
        from app.models.pension_fund import PensionFund
        from app.models.scenario import Scenario
        from app.providers.tax_params import InMemoryTaxParamsProvider
        from app.schemas.tax_schemas import PersonalDetails, TaxCalculationInput
        from app.services.additional_income_service import AdditionalIncomeService
        from app.services.llm_agent_tools.utils import _to_jsonable
        from app.services.rights_fixation.exemption_caps import get_monthly_cap
        from app.services.tax_calculator import TaxCalculator
        from app.utils.date_serializer import parse_date_flexible

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                "result": {},
                "explanation": "לא נמצא לקוח.",
            }

        if desired_net_income is None:
            return {
                "success": False,
                "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                "result": {},
                "explanation": "לא סופק יעד הכנסה נטו.",
            }

        # אם לא סופקה קצבה, נסה לקחת מהתרחישים
        if guaranteed_pension is None:
            scenarios = (
                self.db.query(Scenario)
                .filter(Scenario.client_id == self.client_id)
                .order_by(Scenario.created_at.desc())
                .first()
            )

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
                guaranteed_pension = sum(
                    float(pf.pension_amount or 0) for pf in pension_funds
                )
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
                monthly_val = float(
                    additional_income_service.calculate_monthly_amount(inc) or 0
                )
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
                exempt_pension_amount_monthly = float(
                    get_monthly_cap(current_year)
                ) * float(exempt_pension_pct)
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
            pension_contributions=float(
                getattr(client, "pension_contributions", 0) or 0
            ),
            study_fund_contributions=float(
                getattr(client, "study_fund_contributions", 0) or 0
            ),
            insurance_premiums=float(getattr(client, "insurance_premiums", 0) or 0),
            charitable_donations=float(getattr(client, "charitable_donations", 0) or 0),
            exempt_pension_amount=exempt_pension_amount_monthly,
            pension_months_in_year=12,
        )

        taxable_additional_monthly = (
            annual_salary_income
            + annual_business_income
            + annual_rental_income
            + annual_interest_income
            + annual_dividend_income
            + annual_other_income
        ) / 12

        monthly_fixed_tax = float(fixed_rate_tax_annual) / 12

        def _net_for_withdrawal(withdrawal_monthly: float) -> tuple[float, float, Any]:
            tax_input_with_w = TaxCalculationInput(
                tax_year=current_year,
                personal_details=personal_details,
                salary_income=annual_salary_income,
                pension_income=gross_monthly_pension * 12,
                rental_income=annual_rental_income,
                business_income=annual_business_income,
                interest_income=annual_interest_income,
                dividend_income=annual_dividend_income,
                other_income=annual_other_income + (float(withdrawal_monthly) * 12),
                pension_contributions=float(
                    getattr(client, "pension_contributions", 0) or 0
                ),
                study_fund_contributions=float(
                    getattr(client, "study_fund_contributions", 0) or 0
                ),
                insurance_premiums=float(getattr(client, "insurance_premiums", 0) or 0),
                charitable_donations=float(
                    getattr(client, "charitable_donations", 0) or 0
                ),
                exempt_pension_amount=exempt_pension_amount_monthly,
                pension_months_in_year=12,
            )

            calculator = TaxCalculator(tax_year=current_year)
            tax_result = calculator.calculate_comprehensive_tax(tax_input_with_w)

            annual_tax = float(tax_result.net_tax)
            monthly_tax = annual_tax / 12

            gross_total_monthly = (
                float(gross_monthly_pension)
                + float(taxable_additional_monthly)
                + float(withdrawal_monthly)
            )
            net_total_monthly = (
                gross_total_monthly - float(monthly_tax) - float(monthly_fixed_tax)
            )
            return float(net_total_monthly), float(monthly_tax), tax_result

        low = 0.0
        try:
            high = max(5000.0, float(desired_net_income) * 2)
        except Exception:
            high = 5000.0

        safety_limit = 500000.0
        while True:
            net_at_high, _, _ = _net_for_withdrawal(high)
            if net_at_high >= float(desired_net_income):
                break
            high *= 2
            if high > safety_limit:
                return {
                    "success": False,
                    "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
                    "result": {
                        "desired_net_income": desired_net_income,
                        "guaranteed_pension": gross_monthly_pension,
                        "fixed_rate_income_monthly": fixed_rate_income_monthly,
                        "fixed_rate_tax_annual": fixed_rate_tax_annual,
                        "exempt_pension_percentage": exempt_pension_pct,
                        "exempt_pension_amount_monthly": exempt_pension_amount_monthly,
                        "portfolio_additional_income_monthly": taxable_additional_monthly,
                    },
                    "explanation": "לא הצלחתי למצוא סכום משיכה ברוטו שמגיע ליעד נטו במסגרת תקרת הבטיחות.",
                }

        for _ in range(40):
            mid = (low + high) / 2
            net_at_mid, _, _ = _net_for_withdrawal(mid)
            if net_at_mid >= float(desired_net_income):
                high = mid
            else:
                low = mid

        required_gross_withdrawal = float(high)
        net_income_estimated, monthly_tax_estimated, final_tax_result = (
            _net_for_withdrawal(required_gross_withdrawal)
        )

        explanation_lines: list[str] = []
        explanation_lines.append("🧾 חישוב משיכה חודשית ברוטו מההון כדי להגיע ליעד נטו")
        explanation_lines.append("")
        explanation_lines.append("**נלקח בחשבון:**")
        explanation_lines.append(
            f"  • קצבה מובטחת חודשית (ברוטו): {gross_monthly_pension:,.0f} ₪"
        )
        if taxable_additional_monthly > 0:
            explanation_lines.append(
                f"  • הכנסות נוספות חייבות למס הכנסה: {taxable_additional_monthly:,.0f} ₪/חודש"
            )
        if fixed_rate_income_monthly > 0:
            explanation_lines.append(
                f"  • הכנסות נוספות במס קבוע: {fixed_rate_income_monthly:,.0f} ₪/חודש"
            )
            explanation_lines.append(
                f"  • מס במסלול קבוע (חודשי): {monthly_fixed_tax:,.0f} ₪"
            )
        if exempt_pension_pct > 0:
            explanation_lines.append(
                f"  • פטור קצבה (אחוז): {exempt_pension_pct*100:.1f}%"
            )

        explanation_lines.append("")
        explanation_lines.append("**תוצאה:**")
        explanation_lines.append(
            f"  • יעד נטו: {float(desired_net_income):,.0f} ₪/חודש"
        )
        explanation_lines.append(
            f"  • משיכה חודשית ברוטו נדרשת (מההון): {required_gross_withdrawal:,.0f} ₪"
        )
        explanation_lines.append(
            f"  • נטו מחושב (כולל מס הכנסה ומס קבוע): {net_income_estimated:,.0f} ₪/חודש"
        )
        explanation_lines.append(
            f"  • מס הכנסה חודשי מחושב: {monthly_tax_estimated:,.0f} ₪"
        )

        return {
            "success": True,
            "tool_name": "CALCULATE_REQUIRED_GROSS_WITHDRAWAL",
            "result": {
                "desired_net_income": desired_net_income,
                "guaranteed_pension": gross_monthly_pension,
                "required_gross_withdrawal": required_gross_withdrawal,
                "net_income_estimated": net_income_estimated,
                "monthly_tax_estimated": monthly_tax_estimated,
                "fixed_rate_income_monthly": fixed_rate_income_monthly,
                "fixed_rate_tax_annual": fixed_rate_tax_annual,
                "portfolio_additional_income_monthly": taxable_additional_monthly,
                "exempt_pension_percentage": exempt_pension_pct,
                "exempt_pension_amount_monthly": exempt_pension_amount_monthly,
                "tax_breakdown": _to_jsonable(
                    getattr(final_tax_result, "tax_breakdown", [])
                ),
                "income_breakdown": _to_jsonable(
                    getattr(final_tax_result, "income_breakdown", [])
                ),
            },
            "explanation": "\n".join(explanation_lines),
        }
