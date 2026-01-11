from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.llm_chat.orchestration_utils import is_no_termination_request

from ..chat_helpers import _is_ignore_blocked_text


def _apply_wants_ignore_blocked_and_portfolio_analysis_messages(
    *,
    request: ChatRequest,
    messages: list[ChatMessage],
    is_portfolio_analysis: bool,
) -> bool:
    wants_ignore_blocked = any(
        _is_ignore_blocked_text(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    wants_ignore_blocked = wants_ignore_blocked or any(
        is_no_termination_request(getattr(m, "content", ""))
        for m in (request.messages or [])
        if getattr(m, "role", None) == "user"
    )

    if wants_ignore_blocked:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "המשתמש אישר להתעלם מיתרות חסומות/יתרות לטיפול במסך עזיבת עבודה ולהמשיך בחישוב רק על מה שניתן. "
                    "אל תשאל שוב לאישור על זה. אל תבצע עזיבת עבודה בשיחה זו, והמשך עם שאר הכלים הרלוונטיים בלבד."
                ),
            )
        )

    if is_portfolio_analysis:
        messages.append(
            ChatMessage(
                role="system",
                content=(
                    "הנחיה: המשתמש ביקש ניתוח תיק. חובה להחזיר ניתוח מיד (Advisory Mode). "
                    "אסור לבצע אימות/בדיקת חוקיות של סכום הפיצויים מול נוסחה או מול 'חובת מעסיק'. "
                    "ברירת מחדל: אסור לפרט מדרגות מס. חריג: אם המשתמש ביקש פרמטרים/מדרגות/תקרות והרצת GET_TAX_PARAMS — מותר לצטט מספרים רק מתוך תוצאת הכלי. "
                    "כאשר אתה מדבר עם המשתמש על הפעולה, השתמש במונח 'עזיבת עבודה' בלבד. "
                    "אם מציגים תרחישים אוטומטיים: הם הערכה גסה/ראשונית בלבד, והצג אותם כ'תרחיש 1/2/3'."
                ),
            )
        )

    return wants_ignore_blocked
