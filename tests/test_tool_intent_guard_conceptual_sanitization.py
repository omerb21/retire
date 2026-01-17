from app.guards.tool_intent_guard import (
    allow_tools_for_intent,
    get_tools_disabled_reason,
    sanitize_words_only_conceptual,
    sanitize_words_only_output,
)
from app.services.llm_chat.intent_classifier import ChatIntent


def test_conceptual_words_only_sanitization_removes_client_leakage_and_tool_markers() -> None:
    msg = "מה ההבדל בין קצבה להון?"
    assert allow_tools_for_intent(msg, ChatIntent.ANALYSIS) is False
    assert get_tools_disabled_reason(msg, ChatIntent.ANALYSIS) == "conceptual"

    raw = (
        "בתיק שלך יש פיצויים וקרן השתלמות.\n"
        "בדיקת מקורות: לא נמצאו מקורות\n"
        "מקור: DB\n"
        "🔧 **פלט כלי:**\n"
        "###TOOL_CALL### {\"tool_name\": \"X\"}\n"
        "קיבלתי. אפשר להמשיך בהסבר מילולי בלבד על בסיס הנתונים שנשלחו.\n"
        "טקסט כללי ארוך שמסביר על ההבדל בין קצבה להון באופן כללי וללא המלצה אישית או מידע פרטני.\n"
    )

    cleaned = sanitize_words_only_output(raw)
    cleaned = sanitize_words_only_conceptual(cleaned)

    assert "בתיק שלך" not in cleaned
    assert "פיצויים" not in cleaned
    assert "קרן השתלמות" not in cleaned
    assert "עזיבת עבודה" not in cleaned
    assert "בדיקת מקורות" not in cleaned
    assert "קיבלתי. אפשר להמשיך" not in cleaned

    assert "🔧" not in cleaned
    assert "###TOOL_CALL###" not in cleaned
