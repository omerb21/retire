import json

from fastapi.responses import StreamingResponse

from app.guards.advice_domain import AdviceDomain
from app.guards.advice_domain_resolver import resolve_advice_domain
from app.services.llm_chat.intent_classifier import ChatIntent, detect_intent
from app.services.llm_chat.orchestration_utils_parts.guards_and_validations import (
    is_general_advisory_request,
)
from app.services.llm_chat.orchestration_utils import (
    is_cashflow_missing_income_followup,
    is_net_pension_request,
    is_retirement_comparison_request,
)


def _maybe_handle_advice_mode(
    *,
    exec_only_active: bool,
    original_user_msg: str,
    computed_data,
    extract_target_net_ils,
):
    def is_advice_request(user_msg: str) -> bool:
        candidate = (user_msg or "").strip()
        if not candidate:
            return False
        return any(
            token in candidate
            for token in (
                "ייעוץ",
                "יעוץ",
                "מה הכי נכון",
                "מה לעשות",
                "מה אתה מציע",
                "תן לי המלצה",
                "המלצה",
                "טיפ כללי",
                "ממליץ",
                "עדיף",
                "כולם עושים ככה",
                "כולם עושים",
                "רואה חשבון אמר לי",
                "אין לי זמן תן תשובה",
                "רק תשובה קצרה",
                "תן לי כיוון",
                "תן כיוון",
                "כיוון",
                "עזוב טפסים",
                "עזוב את זה",
                "עזוב מערכת",
                "כן או לא",
                "נכון או לא נכון",
                "טעות או לא טעות",
                "רק מילה אחת",
                "תענה רק",
                "תגיד רק",
                "רק תגיד",
                "רק תענה",
                "זה נכון",
                "זה לא נכון",
                "זו טעות",
                "לא טעות",
                "זה בסדר",
                "זה לא בסדר",
            )
        )

    def _is_report_request_for_early_block(user_msg: str) -> bool:
        lowered = ((user_msg or "").strip()).lower()
        return any(
            token in lowered
            for token in (
                "דוח",
                'דו"ח',
                "שלח דוח",
                "הפק דוח",
                "pdf",
                "report",
            )
        )

    advice_mode = (
        (not exec_only_active)
        and is_advice_request(original_user_msg)
        and (not _is_report_request_for_early_block(original_user_msg))
    )

    resolved_intent = detect_intent(original_user_msg)

    advice_domain = AdviceDomain.UNKNOWN
    if advice_mode:
        advice_domain = resolve_advice_domain(original_user_msg or "")

    if advice_mode and advice_domain == AdviceDomain.COMMUTATION:

        def _advice_commutation_questions():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: הבהרה לפני היוון\n\n"
                "כדי להמשיך אני צריך 3 הבהרות קצרות:\n"
                "- איזו קצבה מדובר (שם קצבה או מספר חשבון/תיק ניכויים)\n"
                "- האם הכוונה ל**סכום חד-פעמי** או ל**הפחתה חודשית מהקצבה**\n"
                "- אם יש כמה קצבאות: לאיזו מהן זה מתייחס?\n"
            )

        return (
            StreamingResponse(
                _advice_commutation_questions(),
                media_type="text/plain",
            ),
            resolved_intent,
            advice_mode,
            advice_domain,
            False,
        )

    if advice_mode and advice_domain == AdviceDomain.FIXATION:

        def _advice_fixation_checklist():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: בדיקת קיבוע זכויות – שלב אבחון\n\n"
                "בדיקות נדרשות:\n"
                "- האם בוצע קיבוע זכויות בעבר\n"
                "- האם התקבלו מענקי פרישה\n"
                "- האם בוצעו היוונים\n"
                "- האם קיימים טפסי 161 / 161ד\n"
                "- מועד פרישה בפועל\n\n"
                "המשמעות:\n"
                "- בלי הנתונים האלו אי אפשר לקבוע פטור קצבה או מס\n\n"
                "פעולה הבאה:\n"
                "- איסוף נתונים והפקת מסמך קיבוע\n"
            )

        return (
            StreamingResponse(
                _advice_fixation_checklist(),
                media_type="text/plain",
            ),
            resolved_intent,
            advice_mode,
            advice_domain,
            False,
        )

    if advice_mode and advice_domain == AdviceDomain.INVESTMENT_RISK:

        def _advice_investment_risk_answer():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: סיכון השקעה בגיל פרישה\n\n"
                "איך סיכון משפיע בגיל פרישה\n"
                "- הסיכון המרכזי הוא תנודתיות סביב נקודת מימוש/משיכה, במיוחד אם מתכננים משיכות בזמן קצר.\n"
                "- ככל שהאופק קצר יותר, תנודות יכולות להכריח שינוי תכנית או דחיית החלטות.\n\n"
                "ההבדל בין תנודתיות לתשואה\n"
                "- תנודתיות מתארת את התזוזה בדרך (עליות/ירידות).\n"
                "- תשואה מתארת את התוצאה לאורך זמן, אך אינה מבטיחה מה יקרה בטווח קצר.\n\n"
                'למה אין מסלול "נכון לכולם"\n'
                "- כי זה תלוי בהרכב מקורות ההכנסה, גמישות תקציבית, צרכים משפחתיים, והיכולת לספוג ירידות.\n\n"
                "מתי כן צריך חישוב\n"
                "- כשיש החלטה אופרטיבית (תזמון משיכה/המרה/שינוי מסלול) או כשיש כמה מקורות הכנסה ורוצים לראות השלכות.\n\n"
                "בלי מספרים. בלי המלצה חד משמעית.\n"
            )

        return (
            StreamingResponse(
                _advice_investment_risk_answer(),
                media_type="text/plain",
            ),
            resolved_intent,
            advice_mode,
            advice_domain,
            False,
        )

    if advice_mode and advice_domain == AdviceDomain.TAX_OPTIMIZATION:

        def _advice_tax_mapping_answer():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: תכנון מס בפרישה – מיפוי ראשוני\n\n"
                "מקורות מס עיקריים בפרישה\n"
                "- קצבאות ותשלומים חודשיים\n"
                "- משיכות הון/מענקים בהתאם למקור ולסיווג\n"
                "- אירועים חד-פעמיים (למשל מענקי פרישה/היוון)\n\n"
                "איפה לרוב נשרף כסף\n"
                "- החלטות שמתבצעות בלי לוודא סטטוסים ומסמכים\n"
                "- חוסר עקביות בין גופים/נתונים שמוביל לבחירות לא נכונות\n\n"
                "מה דורש חישוב מדויק\n"
                "- כל החלטה שיש לה רכיב מס בפועל (נטו/ברוטו), במיוחד כשיש שילוב של כמה מקורות\n\n"
                "אילו החלטות בלתי הפיכות\n"
                "- בחירות שמוגשות למסמכי מס/קיבוע/היוון ושמשנות את מצב הזכויות\n"
            )

        return (
            StreamingResponse(
                _advice_tax_mapping_answer(),
                media_type="text/plain",
            ),
            resolved_intent,
            advice_mode,
            advice_domain,
            False,
        )

    if advice_mode and advice_domain == AdviceDomain.UNKNOWN:

        def _advice_unknown_domain_questions():
            if computed_data is not None:
                computed_json = json.dumps(
                    {"type": "computed_data", "data": computed_data.model_dump()},
                    ensure_ascii=False,
                )
                yield f"###COMPUTED_DATA###{computed_json}###END_COMPUTED_DATA###\n"
            yield (
                "כותרת: הבהרה לפני ייעוץ\n\n"
                "כדי לבחור את הזרימה הנכונה אני צריך להבין על מה השאלה: \n"
                "- פיצויים / מענק פרישה\n"
                "- היוון קצבה\n"
                "- קיבוע זכויות / 161ד\n"
                "- סיכון השקעה / מסלול השקעה\n"
                "- תכנון מס\n\n"
                "כתוב משפט קצר עם אחד מהנושאים (אפשר גם לצרף שאלה)."
            )

        return (
            StreamingResponse(
                _advice_unknown_domain_questions(),
                media_type="text/plain",
            ),
            resolved_intent,
            advice_mode,
            advice_domain,
            False,
        )

    advice_compensation_mode = advice_mode and (
        advice_domain == AdviceDomain.COMPENSATION
    )
    if advice_compensation_mode and is_general_advisory_request(original_user_msg):
        return None, ChatIntent.NO_TOOLS, False, AdviceDomain.UNKNOWN, False
    if advice_compensation_mode:
        resolved_intent = ChatIntent.ANALYSIS

    if advice_compensation_mode:
        lowered_for_advice_gate = (original_user_msg or "").strip().lower()
        explicit_cashflow_in_advice = ("תזרים" in lowered_for_advice_gate) or (
            "cashflow" in lowered_for_advice_gate
        )
        explicit_net_in_advice = is_net_pension_request(original_user_msg)
        explicit_compare_in_advice = is_retirement_comparison_request(original_user_msg)
        explicit_target_net_in_advice = (
            extract_target_net_ils(original_user_msg or "") is not None
        )
        explicit_refresh_in_advice = is_cashflow_missing_income_followup(
            original_user_msg
        )
        if not (
            explicit_cashflow_in_advice
            or explicit_net_in_advice
            or explicit_compare_in_advice
            or explicit_target_net_in_advice
            or explicit_refresh_in_advice
        ):
            advice_block_message = (
                "כדי לענות על זה בצורה נכונה אני צריך להריץ חישוב במערכת הפרישה. "
                "אני יכול להסביר את העיקרון בלבד, בלי מספרים ובלי המלצה."
            )
            return (
                StreamingResponse(
                    iter([advice_block_message]),
                    media_type="text/plain",
                ),
                resolved_intent,
                advice_mode,
                advice_domain,
                advice_compensation_mode,
            )

    return None, resolved_intent, advice_mode, advice_domain, advice_compensation_mode
