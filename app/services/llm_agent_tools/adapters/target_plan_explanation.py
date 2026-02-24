import logging
from typing import Any, Optional

logger = logging.getLogger("app.llm_agent_tools")


def build_target_pension_plan_explanation(
    *,
    target_achieved_gross: bool,
    target: float,
    target_is_net: bool,
    retirement_age: int,
    plan_steps: list[dict[str, Any]],
    remaining_capital: float,
    advantages: list[str],
    disadvantages: list[str],
    blocked_for_execution_capital: float,
    accumulated_pension: float,
    estimated_net: Optional[float],
    gap: float,
    required_gross_for_target: float,
    exempt_pension: float,
    avg_factor: float,
) -> str:
    # בניית הסבר מפורט לסוכן
    explanation_parts: list[str] = []

    if target_achieved_gross:
        explanation_parts.append(
            (
                f"✅ **התכנית הושלמה בהצלחה** - ניתן להגיע לקצבה של {target:,.0f} ₪ נטו (משוער) בגיל {retirement_age}."
                if target_is_net
                else f"✅ **התכנית הושלמה בהצלחה** - ניתן להגיע לקצבה של {target:,.0f} ₪/חודש בגיל {retirement_age}."
            )
        )
        explanation_parts.append("")
        explanation_parts.append("**📋 צעדי התכנית:**")
        for step in plan_steps:
            explanation_parts.append(
                f"  {step['step_number']}. {step['source_name']} (מקדם {step['annuity_factor']:.0f}): "
                f"+{step['pension_added']:,.0f} ₪/חודש → סה\"כ {step['accumulated_pension']:,.0f} ₪"
            )

        if remaining_capital > 0:
            explanation_parts.append("")
            explanation_parts.append(
                f"💰 **הון שנותר**: {remaining_capital:,.0f} ₪ (לא הומר לקצבה)"
            )

        if advantages:
            explanation_parts.append("")
            explanation_parts.append("**✅ יתרונות:**")
            for adv in advantages:
                explanation_parts.append(f"  • {adv}")

        if disadvantages:
            explanation_parts.append("")
            explanation_parts.append("**⚠️ חסרונות:**")
            for dis in disadvantages:
                explanation_parts.append(f"  • {dis}")

        if blocked_for_execution_capital > 0:
            explanation_parts.append("")
            explanation_parts.append(
                "**🧩 מקורות שדורשים עזיבת עבודה כדי לכלול בפועל:**"
            )
            explanation_parts.append(
                f'  • הון חסום לביצוע (סה"כ): {blocked_for_execution_capital:,.0f} ₪'
            )

        # המלצות נוספות
        explanation_parts.append("")
        explanation_parts.append("**💡 המלצות:**")
        if remaining_capital > 100000:
            explanation_parts.append(
                f"  • ההון שנותר ({remaining_capital:,.0f} ₪) יכול לשמש כרזרבה לחירום או להעברה לדור הבא."
            )
        if exempt_pension > 0:
            explanation_parts.append(
                f"  • {exempt_pension:,.0f} ₪ מהקצבה פטורים ממס - יתרון משמעותי."
            )
        if avg_factor > 190:
            explanation_parts.append(
                "  • שקול לדחות את הפרישה בשנה-שנתיים לשיפור המקדם."
            )
    else:
        explanation_parts.append(
            (
                f"❌ **לא ניתן להגיע ליעד** של {target:,.0f} ₪ נטו (משוער) עם המקורות הקיימים."
                if target_is_net
                else f"❌ **לא ניתן להגיע ליעד** של {target:,.0f} ₪/חודש עם המקורות הקיימים."
            )
        )
        explanation_parts.append("")
        explanation_parts.append(f"📊 **המצב הנוכחי:**")
        explanation_parts.append(
            f"  • קצבה ברוטו שנבנתה מהמקורות: {accumulated_pension:,.0f} ₪/חודש"
        )
        if target_is_net and estimated_net is not None:
            explanation_parts.append(
                f"  • קצבה נטו משוערת (מס הכנסה בלבד): {float(estimated_net):,.0f} ₪/חודש"
            )
        explanation_parts.append(f"  • פער מהיעד: {gap:,.0f} ₪/חודש")
        base = required_gross_for_target if required_gross_for_target > 0 else 1
        explanation_parts.append(
            f"  • אחוז מהיעד: {(accumulated_pension/base*100):.0f}%"
        )

        explanation_parts.append("")
        explanation_parts.append("**💡 אפשרויות לגישור הפער:**")
        explanation_parts.append(
            f"  1. **דחיית פרישה**: כל שנה נוספת משפרת את המקדם ומגדילה את הצבירה."
        )
        explanation_parts.append(f"  2. **הגדלת חיסכון**: הפקדות נוספות עד הפרישה.")
        explanation_parts.append(
            f"  3. **הורדת יעד**: יעד ריאלי יותר הוא {accumulated_pension:,.0f} ₪/חודש."
        )
        if remaining_capital > 0:
            monthly_from_capital = remaining_capital / 240  # 20 שנות פרישה
            explanation_parts.append(
                f"  4. **משיכה מההון**: {remaining_capital:,.0f} ₪ יכולים לתת ~{monthly_from_capital:,.0f} ₪/חודש ל-20 שנה."
            )

    return "\n".join(explanation_parts)
