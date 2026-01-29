from fastapi.responses import StreamingResponse


def _maybe_handle_general_retirement_help(*, original_user_msg: str, is_general_retirement_help_request):
    if not is_general_retirement_help_request(original_user_msg):
        return None

    def _general_retirement_help_answer():
        yield (
            "כותרת: תכנון פרישה – מיפוי ראשוני\n\n"
            "כדי לעזור לך לתכנן נכון, אני צריך קודם למפות את התמונה: מקורות הכנסה, הוצאות, הון נזיל, והחלטות שעומדות על הפרק.\n\n"
            "שאלות קצרות כדי להתקדם:\n"
            "- מה יעד ההכנסה החודשית שאתה רוצה להגיע אליו (במילים: נטו או ברוטו)?\n"
            "- מה מקורות ההכנסה שיש לך כרגע (קצבאות, עבודה חלקית, שכירות, הכנסות נוספות)?\n"
            "- האם יש לך הון נזיל או סכומים חד-פעמיים שצפויים להיכנס/לצאת בתקופה הקרובה?\n"
            "- האם יש הוצאות חריגות/צרכים מיוחדים שחשוב לקחת בחשבון?\n\n"
            "אפשרויות פעולה במערכת (לבחירה שלך):\n"
            "- לחשב תזרים לפי יעד שתגדיר\n"
            "- להפיק דוח מסכם\n"
            "- לבנות תכנית יעד קצבה אחרי שתציין יעד חודשי\n"
        )

    return StreamingResponse(
        _general_retirement_help_answer(),
        media_type="text/plain; charset=utf-8",
    )


def _maybe_handle_general_retirement_intro(*, original_user_msg: str, is_general_retirement_intro_request):
    if not is_general_retirement_intro_request(original_user_msg):
        return None

    def _general_retirement_intro_answer():
        yield (
            "כותרת: תכנון פרישה – מיפוי ראשוני\n\n"
            "כדי להתקדם בצורה מסודרת, נתחיל במיפוי קצר ואז נבחר פעולה במערכת.\n\n"
            "שאלות קצרות כדי להתקדם:\n"
            "- מה יעד ההכנסה החודשית שאתה רוצה להגיע אליו (במילים: נטו או ברוטו)?\n"
            "- אילו מקורות הכנסה יש לך כרגע (קצבאות, עבודה חלקית, שכירות, הכנסות נוספות)?\n"
            "- האם יש הון נזיל/סכומים חד-פעמיים קרובים?\n"
            "- האם יש אירוע עזיבת עבודה שצריך לעבד במערכת (ביצוע רק אם תבקש)?\n\n"
            "אפשרויות פעולה במערכת (לבחירה שלך):\n"
            "- לחשב תזרים לפי יעד שתגדיר\n"
            "- לבנות תכנית יעד קצבה אחרי שתציין יעד חודשי\n"
            "- להפיק דוח מסכם\n"
        )

    return StreamingResponse(
        _general_retirement_intro_answer(),
        media_type="text/plain; charset=utf-8",
    )


def _maybe_handle_explain_in_words(
    *,
    original_user_msg: str,
    request,
    db,
    is_explain_in_words_request,
    extract_latest_target_pension_plan_payload,
    load_latest_target_pension_plan_data,
    load_latest_target_pension_plan,
 ):
    if not is_explain_in_words_request(original_user_msg):
        return None

    def _explain_in_words_answer():
        plan_payload = None
        try:
            plan_payload = extract_latest_target_pension_plan_payload(request.messages)
        except Exception:
            plan_payload = None
        if request.client_id is not None:
            try:
                plan_payload = load_latest_target_pension_plan_data(
                    db=db, client_id=request.client_id
                )
            except Exception:
                plan_payload = None
            if plan_payload is None:
                try:
                    plan_payload = load_latest_target_pension_plan(
                        db=db, client_id=request.client_id
                    )
                except Exception:
                    plan_payload = None

        plan_res = (
            plan_payload.get("result")
            if isinstance(plan_payload, dict) and isinstance(plan_payload.get("result"), dict)
            else None
        )
        if isinstance(plan_res, dict):
            target_achieved = plan_res.get("target_achieved")
            gap_to_target = plan_res.get("gap_to_target")
            has_gap = False
            if isinstance(gap_to_target, (int, float)):
                has_gap = gap_to_target > 0

            if target_achieved is True:
                status_line = "- לפי תוצאת התכנית האחרונה שנבנתה במערכת: היעד הושג."
            elif has_gap:
                status_line = "- לפי תוצאת התכנית האחרונה שנבנתה במערכת: קיים פער ליעד."
            else:
                status_line = "- לפי תוצאת התכנית האחרונה שנבנתה במערכת: לא ניתן לקבוע כאן אם היעד הושג או אם קיים פער."

            yield (
                "כותרת: הסבר במילים לתוצאת התכנית האחרונה\n\n"
                "מה זה אומר\n"
                + status_line
                + "\n\n"
                "צעד הבא\n"
                "- אם תרצה לעדכן יעד/גיל פרישה או לשנות הנחות, יש לבנות תכנית חדשה ואז להציג תזרים מתוך תוצאת התכנית.\n"
            )
            return

        yield (
            "כותרת: הסבר במילים\n\n"
            "אין תוצאת תכנית אחרונה להצמד אליה, ולכן ההסבר כאן הוא עקרונות כלליים בלבד.\n\n"
            "איך ניגשים לתכנון פרישה באופן כללי\n"
            "- מיפוי מקורות הכנסה והאם הם קבועים או משתנים\n"
            "- מיפוי הוצאות שוטפות והוצאות חד-פעמיות צפויות\n"
            "- הבחנה בין הכנסה נטו לברוטו והשפעת המס\n"
            "- בדיקת פער בין היעד לבין ההכנסה והחלטה אם משלימים מהון\n"
            "- זיהוי החלטות בלתי הפיכות מול החלטות שניתנות לשינוי\n\n"
            "כדי שאוכל להסביר על סמך חישוב מערכת, יש לבנות תכנית תחילה.\n"
        )

    return StreamingResponse(
        _explain_in_words_answer(),
        media_type="text/plain; charset=utf-8",
    )


def _maybe_handle_general_retirement_responses(
    *,
    original_user_msg: str,
    request,
    db,
    is_general_retirement_help_request,
    is_general_retirement_intro_request,
    is_explain_in_words_request,
    extract_latest_target_pension_plan_payload,
    load_latest_target_pension_plan_data,
    load_latest_target_pension_plan,
 ):
    resp = _maybe_handle_general_retirement_help(
        original_user_msg=original_user_msg,
        is_general_retirement_help_request=is_general_retirement_help_request,
    )
    if resp is not None:
        return resp

    resp = _maybe_handle_general_retirement_intro(
        original_user_msg=original_user_msg,
        is_general_retirement_intro_request=is_general_retirement_intro_request,
    )
    if resp is not None:
        return resp

    resp = _maybe_handle_explain_in_words(
        original_user_msg=original_user_msg,
        request=request,
        db=db,
        is_explain_in_words_request=is_explain_in_words_request,
        extract_latest_target_pension_plan_payload=extract_latest_target_pension_plan_payload,
        load_latest_target_pension_plan_data=load_latest_target_pension_plan_data,
        load_latest_target_pension_plan=load_latest_target_pension_plan,
    )
    if resp is not None:
        return resp

    return None
