import logging
from typing import Any, Dict

logger = logging.getLogger("app.llm_agent_tools")


class CommutationToolsMixin:
    def calculate_pension_commutation(
        self,
        target_monthly_pension_reduction: float,
        retirement_date: str,
    ) -> Dict[str, Any]:
        """
        מחשב היוון קצבה - המרת חלק מהקצבה החודשית לסכום חד-פעמי.
        
        Args:
            target_monthly_pension_reduction: הסכום החודשי שהלקוח מוכן להפחית מהקצבה (ברוטו)
            retirement_date: תאריך הפרישה (YYYY-MM-DD)
            
        Returns:
            Dict עם סכום ההיוון ברוטו, מס, ונטו
        """
        from app.services.annuity_coefficient import get_annuity_coefficient
        from app.services.commutation_service import CommutationService
        from app.utils.date_serializer import parse_date_flexible

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        if not client.birth_date:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": "חסר תאריך לידה ללקוח - לא ניתן לחשב מקדמי קצבה.",
            }

        # פרסור תאריך פרישה
        try:
            ret_date = parse_date_flexible(retirement_date)
        except Exception:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": f"תאריך פרישה לא תקין: {retirement_date}. יש להזין בפורמט YYYY-MM-DD.",
            }

        # חישוב גיל פרישה
        age_at_retirement = ret_date.year - client.birth_date.year
        if (ret_date.month, ret_date.day) < (client.birth_date.month, client.birth_date.day):
            age_at_retirement -= 1

        current_age = client.get_age() if hasattr(client, 'get_age') else None
        if current_age and age_at_retirement < current_age:
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": f"גיל הפרישה ({age_at_retirement}) לא יכול להיות נמוך מהגיל הנוכחי ({current_age}).",
            }

        # קבלת מקדם קצבה ממוצע
        gender = client.gender or 'זכר'
        try:
            from datetime import date

            coeff_result = get_annuity_coefficient(
                product_type='קרן פנסיה',
                start_date=date.today(),
                gender=gender,
                retirement_age=age_at_retirement,
                survivors_option='תקנוני',
                birth_date=client.birth_date,
                pension_start_date=ret_date,
            )
            annuity_factor = float(coeff_result.get('factor_value', 200))
        except Exception:
            annuity_factor = 200.0

        # חישוב הכנסה שנתית אחרת (אם יש)
        other_annual_income = 0.0
        if client.annual_salary:
            other_annual_income = float(client.annual_salary)

        # ביצוע חישוב ההיוון
        commutation_service = CommutationService(self.db, self.client_id)
        result = commutation_service.calculate(
            monthly_pension_reduction=target_monthly_pension_reduction,
            annuity_factor=annuity_factor,
            client_age=current_age or age_at_retirement,
            retirement_age=age_at_retirement,
            gender=gender,
            other_annual_income=other_annual_income,
        )

        if not result.get('success'):
            return {
                "success": False,
                "tool_name": "CALCULATE_PENSION_COMMUTATION",
                "result": {},
                "explanation": result.get('error', 'שגיאה בחישוב ההיוון'),
            }

        # בניית הסבר מפורט
        explanation_lines = [
            f"💰 **חישוב היוון קצבה**",
            f"",
            f"**פרטי ההיוון:**",
            f"  • הפחתה חודשית מהקצבה: {result['monthly_pension_reduction']:,.0f} ₪",
            f"  • מקדם קצבה: {result['annuity_factor']:.1f}",
            f"  • גיל פרישה: {age_at_retirement}",
            f"",
            f"**סכום ההיוון:**",
            f"  • סכום ברוטו: {result['lump_sum_gross']:,.0f} ₪",
            f"  • מס הכנסה על ההיוון: {result['tax_on_lump_sum']:,.0f} ₪ ({result['effective_tax_rate']:.1f}%)",
            f"  • **סכום נטו: {result['lump_sum_net']:,.0f} ₪**",
            f"",
            f"**השוואה כלכלית:**",
            f"  • קצבה שנתית שתאבד: {result['annual_pension_lost']:,.0f} ₪",
            f"  • סה\"כ קצבה שתאבד ב-30 שנה: {result['total_pension_lost_30_years']:,.0f} ₪",
            f"  • ערך נוכחי (NPV) של הקצבה שתאבד: {result['npv_pension_lost']:,.0f} ₪",
            f"",
        ]

        comparison = result.get('comparison', {})
        if comparison.get('recommendation') == 'lump_sum':
            explanation_lines.append(f"✅ **המלצה:** ההיוון משתלם כלכלית (הפרש: {comparison['difference']:,.0f} ₪ לטובתך)")
        else:
            explanation_lines.append(f"⚠️ **המלצה:** הקצבה משתלמת יותר כלכלית (הפרש: {abs(comparison['difference']):,.0f} ₪)")

        explanation_lines.extend([
            f"",
            f"**💡 שים לב:**",
            f"  • ההיוון מתאים למי שצריך סכום גדול מיידי (למשל לפירעון משכנתא)",
            f"  • הקצבה מתאימה למי שמעדיף הכנסה קבועה לכל החיים",
        ])

        return {
            "success": True,
            "tool_name": "CALCULATE_PENSION_COMMUTATION",
            "result": {
                "retirement_date": retirement_date,
                "retirement_age": age_at_retirement,
                "monthly_pension_reduction": result['monthly_pension_reduction'],
                "annuity_factor": result['annuity_factor'],
                "lump_sum_gross": result['lump_sum_gross'],
                "tax_on_lump_sum": result['tax_on_lump_sum'],
                "lump_sum_net": result['lump_sum_net'],
                "effective_tax_rate": result['effective_tax_rate'],
                "annual_pension_lost": result['annual_pension_lost'],
                "npv_pension_lost": result['npv_pension_lost'],
                "recommendation": comparison.get('recommendation', 'unknown'),
            },
            "explanation": "\n".join(explanation_lines),
        }
