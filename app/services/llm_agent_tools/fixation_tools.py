import logging
from typing import Any, Dict

logger = logging.getLogger("app.llm_agent_tools")


class FixationToolsMixin:
    def calculate_tax_exempt_pension(self, current_tax_exempt_grant_amount: float) -> Dict[str, Any]:
        """
        מבצע סימולציה של חישוב קיבוע זכויות (Tax Relief) והשפעת משיכת מענק פטור.
        מחשב את הקצבה הפטורה לפני ואחרי קיזוז המענק המבוקש.
        """
        from app.models.fixation_result import FixationResult
        
        # קבועים לחישוב (נכון ל-2025)
        QUALIFYING_PENSION_CAP = 9924  # תקרת קצבה מזכה משוערת ל-2025
        EXEMPTION_RATE = 0.52          # שיעור הפטור (52%)
        OFFSET_FACTOR = 1.35           # מקדם קיזוז למענקים (נוסחת הקיזוז)
        CAPITALIZATION_FACTOR = 180    # מקדם המרה להון (180 משכורות)
        
        # 1. שליפת נתונים קיימים או חישוב ברירת מחדל
        fixation = self.db.query(FixationResult).filter(
            FixationResult.client_id == self.client_id
        ).first()

        if fixation and fixation.exempt_capital_remaining > 0:
            total_exempt_capital = fixation.exempt_capital_remaining
            source = "FixationResult (DB)"
        else:
            # חישוב ברירת מחדל אם אין קיבוע היסטורי
            monthly_exemption = QUALIFYING_PENSION_CAP * EXEMPTION_RATE
            total_exempt_capital = monthly_exemption * CAPITALIZATION_FACTOR
            source = "Default (2025 Estimation)"

        # 2. חישוב קצבה פטורה התחלתית (ללא משיכת המענק הנוכחי)
        # אם יש מענקים קודמים, הם כבר מגולמים ב-exempt_capital_remaining
        initial_exempt_pension = total_exempt_capital / CAPITALIZATION_FACTOR

        # 3. סימולציה: קיזוז המענק הנוכחי
        # כל שקל מענק מקזז 1.35 שקל מההון הפטור
        grant_offset_value = current_tax_exempt_grant_amount * OFFSET_FACTOR
        remaining_capital_after_grant = max(0, total_exempt_capital - grant_offset_value)
        
        final_exempt_pension = remaining_capital_after_grant / CAPITALIZATION_FACTOR

        # 4. הכנת תוצאה
        monthly_loss = initial_exempt_pension - final_exempt_pension
        
        # פורמט טקסטואלי לתשובה
        scenario_a = (
            f"תרחיש A (שמירת הפטור לקצבה):\n"
            f"• סה\"כ הון פטור זמין: {total_exempt_capital:,.0f} ₪\n"
            f"• קצבה פטורה חודשית: {initial_exempt_pension:,.0f} ₪"
        )
        
        scenario_b = (
            f"תרחיש B (משיכת מענק פטור בסך {current_tax_exempt_grant_amount:,.0f} ₪):\n"
            f"• עלות הקיזוז בהון: {grant_offset_value:,.0f} ₪ (לפי מקדם 1.35)\n"
            f"• הון פטור נותר: {remaining_capital_after_grant:,.0f} ₪\n"
            f"• קצבה פטורה חודשית: {final_exempt_pension:,.0f} ₪"
        )
        
        explanation = (
            f"בוצעה סימולציית קיבוע זכויות ({source}).\n"
            f"משיכת מענק של {current_tax_exempt_grant_amount:,.0f} ₪ תקטין את הקצבה הפטורה ב-{monthly_loss:,.0f} ₪ לכל החיים."
        )

        return {
            "success": True,
            "tool_name": "CALCULATE_TAX_EXEMPT_PENSION",
            "result": {
                "initial_exempt_pension": round(initial_exempt_pension, 2),
                "final_exempt_pension": round(final_exempt_pension, 2),
                "exempt_grant_used": current_tax_exempt_grant_amount,
                "monthly_pension_loss": round(monthly_loss, 2),
                "total_capital_offset": round(grant_offset_value, 2),
                "remaining_exempt_capital": round(remaining_capital_after_grant, 2),
                "scenarios_text": {
                    "scenario_a": scenario_a,
                    "scenario_b": scenario_b,
                }
            },
            "explanation": explanation
        }
