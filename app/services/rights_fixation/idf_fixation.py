"""
מודול חישוב פגיעה בהון הפטור לפורשי צה"ל וכוחות ביטחון.

החישוב מתבסס אך ורק על:
- סכום הפחתה חודשי בפועל בתלוש במועד הזכאות (reduction_amount).
- אחוז היוון מקורי (original_commutation_percent).
- אחוז היוון נוכחי (current_commutation_percent).
- תקרת קצבה מזכה חודשית לשנת הזכאות (monthly_cap).
- תקופת חפיפה בחודשים בין תאריך הזכאות לבין גיל המקדם.

אין שימוש בחישובי היוון הוני, מדדים, 32 שנים או מכנה 180.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional, Union


DateLike = Union[str, date]


@dataclass
class IdfFixationResult:
    """תוצאת חישוב פגיעה בהון הפטור לפורשי צה"ל.

    impact: סכום פגיעה בהון הפטור (יכול להיות 0).
    overlap_months: מספר חודשי החפיפה שנלקחו בחשבון.
    base_reduction: סכום ההפחתה החודשי לאחר התאמה לאחוז המקורי.
    monthly_reduction_for_calc: סכום ההפחתה החודשי לאחר החלת כלל 35% מהתקרה.
    error: טקסט שגיאה לוגית במידת הצורך (למשל חוסר נתונים / אין תקופה חופפת).
    """

    impact: float
    overlap_months: int
    base_reduction: float
    monthly_reduction_for_calc: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "impact": self.impact,
            "overlap_months": self.overlap_months,
            "base_reduction": self.base_reduction,
            "monthly_reduction_for_calc": self.monthly_reduction_for_calc,
            "error": self.error,
        }


def _parse_date(value: DateLike, field_name: str) -> date:
    """המרת מחרוזת YYYY-MM-DD או date לאובייקט date.

    במידה ולא ניתן להמיר – מעלה ValueError עם הודעה בעברית.
    """

    if isinstance(value, date):
        return value

    if not isinstance(value, str) or not value:
        raise ValueError(f"שגיאה בנתון תאריך עבור {field_name} – הערך חסר או לא תקין")

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        raise ValueError(f"שגיאה בנתון תאריך עבור {field_name} – פורמט לא תקין (נדרש YYYY-MM-DD)")


def _months_between(start: date, end: date) -> int:
    """מספר חודשים שלמים בין שני תאריכים.

    אם יום הסיום קטן מיום ההתחלה – מפחיתים חודש אחד (כלומר נספרים רק חודשים שהושלמו).
    התוצאה יכולה להיות 0 או שלילית; האחריות על בדיקה חיצונית.
    """

    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


def compute_idf_fixation_impact(
    *,
    reduction_amount: Optional[float],
    original_commutation_percent: Optional[float],
    current_commutation_percent: Optional[float],
    monthly_cap: Optional[float],
    eligibility_date: DateLike,
    commutation_date: DateLike,
    promoter_age_date: DateLike,
) -> IdfFixationResult:
    """חישוב פגיעה בהון הפטור לפורשי צה"ל לפי ההנחיות שהוגדרו.

    שלבים:
    1. חישוב base_reduction = reduction_amount * (original_percent / current_percent).
    2. חישוב max_reduction = 35% * monthly_cap.
    3. בחירת monthly_reduction_for_calc = min(base_reduction, max_reduction).
    4. חישוב תקופת חפיפה בחודשים שלמים בין:
       overlap_start = max(eligibility_date, commutation_date)
       overlap_end = promoter_age_date
    5. פגיעה בהון הפטור = monthly_reduction_for_calc * overlap_months.

    במקרי חוסר נתונים או חוסר תקופת חפיפה:
    - הפגיעה מחושבת כ-0.
    - מחזירים error עם הודעה ברורה בעברית.
    """

    # ברירת מחדל – פגיעה 0 עד שיוכח אחרת
    zero_result = IdfFixationResult(
        impact=0.0,
        overlap_months=0,
        base_reduction=0.0,
        monthly_reduction_for_calc=0.0,
        error=None,
    )

    # בדיקת נתוני אחוזים וסכום הפחתה
    if (
        reduction_amount is None
        or original_commutation_percent is None
        or current_commutation_percent is None
    ):
        zero_result.error = (
            "חסרים נתוני הפחתה (סכום / אחוז היוון מקורי / אחוז היוון נוכחי) "
            "לחישוב לפי פורשי צה""ל"
        )
        return zero_result

    try:
        reduction_amount_f = float(reduction_amount)
        original_percent_f = float(original_commutation_percent)
        current_percent_f = float(current_commutation_percent)
    except (TypeError, ValueError):
        zero_result.error = (
            "חסרים או שגויים נתוני הפחתה (סכום / אחוז היוון מקורי / אחוז היוון נוכחי)"
        )
        return zero_result

    if reduction_amount_f <= 0 or original_percent_f <= 0 or current_percent_f <= 0:
        zero_result.error = (
            "חסרים נתוני הפחתה (סכום / אחוז היוון מקורי / אחוז היוון נוכחי) לחישוב לפי פורשי צה""ל"
        )
        return zero_result

    if monthly_cap is None:
        zero_result.error = "חסרה תקרת קצבה מזכה חודשית לחישוב לפי פורשי צה""ל"
        return zero_result

    try:
        monthly_cap_f = float(monthly_cap)
    except (TypeError, ValueError):
        zero_result.error = "תקרת הקצבה המזכה החודשית אינה מספר תקין"
        return zero_result

    if monthly_cap_f <= 0:
        zero_result.error = "תקרת הקצבה המזכה החודשית צריכה להיות גדולה מאפס"
        return zero_result

    # התאמת ההפחתה החודשית לאחוז המקורי
    try:
        base_reduction = reduction_amount_f * (original_percent_f / current_percent_f)
    except ZeroDivisionError:
        zero_result.error = "אחוז היוון נוכחי שווה לאפס – לא ניתן לחשב הפחתה"
        return zero_result

    if base_reduction <= 0:
        zero_result.error = "חישוב ההפחתה החודשית לאחר התאמה הביא לתוצאה לא חיובית"
        return zero_result

    # כלל 35% – תקרה על ההפחתה החודשית בלבד
    max_reduction = monthly_cap_f * 0.35
    monthly_reduction_for_calc = min(base_reduction, max_reduction)

    # חישוב תאריכי חפיפה
    try:
        elig_dt = _parse_date(eligibility_date, "תאריך הזכאות")
        comm_dt = _parse_date(commutation_date, "תאריך ההיוון")
        prom_dt = _parse_date(promoter_age_date, "תאריך גיל המקדם")
    except ValueError as e:
        # חוסר/שגיאה באחד התאריכים נחשבת חריגה לוגית – החישוב נעצר
        return IdfFixationResult(
            impact=0.0,
            overlap_months=0,
            base_reduction=base_reduction,
            monthly_reduction_for_calc=monthly_reduction_for_calc,
            error=str(e),
        )

    overlap_start = max(elig_dt, comm_dt)
    overlap_end = prom_dt

    if overlap_end <= overlap_start:
        return IdfFixationResult(
            impact=0.0,
            overlap_months=0,
            base_reduction=base_reduction,
            monthly_reduction_for_calc=monthly_reduction_for_calc,
            error="אין תקופה חופפת בין תאריך הזכאות לבין גיל המקדם עבור ההיוון שנבחר",
        )

    overlap_months = _months_between(overlap_start, overlap_end)
    if overlap_months <= 0:
        return IdfFixationResult(
            impact=0.0,
            overlap_months=overlap_months,
            base_reduction=base_reduction,
            monthly_reduction_for_calc=monthly_reduction_for_calc,
            error="אין תקופה חופפת בין תאריך הזכאות לבין גיל המקדם עבור ההיוון שנבחר",
        )

    impact = round(monthly_reduction_for_calc * overlap_months, 2)

    return IdfFixationResult(
        impact=impact,
        overlap_months=overlap_months,
        base_reduction=base_reduction,
        monthly_reduction_for_calc=monthly_reduction_for_calc,
        error=None,
    )
