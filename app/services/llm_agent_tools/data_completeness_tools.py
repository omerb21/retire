from typing import Any, Dict, List


class DataCompletenessToolsMixin:
    def check_data_completeness(self) -> Dict[str, Any]:
        """בודק אם כל הנתונים הנדרשים לחישוב תרחישים קיימים"""
        from app.models.current_employment.employer import CurrentEmployer
        from app.models.fixation_result import FixationResult
        from app.models.pension_fund import PensionFund
        from app.models.scenario import Scenario

        missing_fields: List[str] = []
        warnings: List[str] = []

        client = self.client
        if not client:
            return {
                "success": False,
                "tool_name": "CHECK_DATA_COMPLETENESS",
                "result": {"complete": False, "missing": ["לקוח לא נמצא"]},
                "explanation": "לא נמצא לקוח עם המזהה שסופק.",
            }

        # בדיקות נתונים קריטיים
        recommendations: list[str] = []

        if not client.birth_date:
            missing_fields.append("תאריך לידה")
            recommendations.append("הזן תאריך לידה בפרטי הלקוח")
        if not client.gender:
            missing_fields.append("מגדר")
            recommendations.append("הזן מגדר בפרטי הלקוח (משפיע על מקדמי קצבה)")
        if not client.annual_salary:
            warnings.append("לא הוגדר שכר שנתי")
            recommendations.append("הזן שכר שנתי לחישוב יעד קצבה מומלץ")

        # בדיקת קיום מוצרים פנסיוניים
        pension_funds = (
            self.db.query(PensionFund)
            .filter(PensionFund.client_id == self.client_id)
            .all()
        )

        if not pension_funds:
            warnings.append("לא נמצאו מוצרים פנסיוניים")
            recommendations.append("העלה תיק פנסיוני (קובץ XML מהמסלקה)")
        else:
            # בדיקה שיש יתרות/מקדמים
            funds_with_balance = [
                pf for pf in pension_funds if pf.balance and pf.balance > 0
            ]
            funds_with_pension = [
                pf
                for pf in pension_funds
                if pf.pension_amount and pf.pension_amount > 0
            ]
            if not funds_with_balance and not funds_with_pension:
                warnings.append("המוצרים הפנסיוניים ללא יתרות או קצבות")
                recommendations.append("וודא שהתיק הפנסיוני מכיל יתרות")

        # בדיקת תרחישים קיימים
        scenarios_count = (
            self.db.query(Scenario).filter(Scenario.client_id == self.client_id).count()
        )

        if scenarios_count == 0:
            warnings.append("לא נמצאו תרחישי פרישה")
            recommendations.append("הרץ תרחישי פרישה לגיל הרצוי")

        # בדיקת קיבוע זכויות
        fixation_exists = (
            self.db.query(FixationResult)
            .filter(FixationResult.client_id == self.client_id)
            .first()
            is not None
        )

        if not fixation_exists:
            warnings.append("לא בוצע קיבוע זכויות")
            recommendations.append("בצע קיבוע זכויות לחישוב פטור ממס")

        # בדיקת מעסיק נוכחי
        employers_count = (
            self.db.query(CurrentEmployer)
            .filter(CurrentEmployer.client_id == self.client_id)
            .count()
        )

        if employers_count == 0:
            warnings.append("לא הוגדר מעסיק נוכחי")
            recommendations.append("הזן פרטי מעסיק נוכחי לחישוב פיצויים")

        is_complete = len(missing_fields) == 0

        # בניית הסבר מפורט
        explanation_parts: list[str] = []

        if is_complete and not warnings:
            explanation_parts.append("✅ **כל הנתונים הנדרשים קיימים!**")
            explanation_parts.append("")
            explanation_parts.append("ניתן להמשיך בחישוב תרחישים ובניית תכניות פרישה.")
            explanation_parts.append(
                f"נמצאו {len(pension_funds)} מוצרים פנסיוניים ו-{scenarios_count} תרחישים שמורים."
            )
        elif is_complete and warnings:
            explanation_parts.append("⚠️ **הנתונים הבסיסיים קיימים, אך יש התראות:**")
            explanation_parts.append("")
            for w in warnings:
                explanation_parts.append(f"  • {w}")
            if recommendations:
                explanation_parts.append("")
                explanation_parts.append("**💡 המלצות:**")
                for r in recommendations[:3]:
                    explanation_parts.append(f"  • {r}")
        else:
            explanation_parts.append("❌ **חסרים נתונים קריטיים:**")
            explanation_parts.append("")
            for m in missing_fields:
                explanation_parts.append(f"  • {m}")
            if warnings:
                explanation_parts.append("")
                explanation_parts.append("**התראות נוספות:**")
                for w in warnings:
                    explanation_parts.append(f"  • {w}")
            explanation_parts.append("")
            explanation_parts.append("**💡 מה לעשות:**")
            for r in recommendations[:5]:
                explanation_parts.append(f"  • {r}")

        explanation = "\n".join(explanation_parts)

        return {
            "success": True,
            "tool_name": "CHECK_DATA_COMPLETENESS",
            "result": {
                "complete": is_complete,
                "missing": missing_fields,
                "warnings": warnings,
                "recommendations": recommendations,
                "pension_funds_count": len(pension_funds),
                "scenarios_count": scenarios_count,
                "fixation_exists": fixation_exists,
                "employers_count": employers_count,
            },
            "explanation": explanation,
        }
