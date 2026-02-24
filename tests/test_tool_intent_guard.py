from app.guards.tool_intent_guard import (
    allow_tools_for_intent,
    sanitize_words_only_output,
)
from app.services.llm_chat.intent_classifier import ChatIntent


def test_conceptual_question_disables_tools() -> None:
    msg = "מה ההבדל בין קיבוע זכויות לבין תכנית משיכה?"
    assert allow_tools_for_intent(msg, ChatIntent.ANALYSIS) is False


def test_words_only_sanitizer_removes_digits_and_tool_blocks() -> None:
    raw = (
        '###TRANSPARENCY_LOG### {"test": true}\n'
        "🔧 **פלט כלי:**\n"
        "סכום: 12345₪\n"
        "open_path: C:/tmp/report_123.pdf\n"
        "טקסט רגיל בלי מספרים\n"
    )
    cleaned = sanitize_words_only_output(raw)
    assert "1" not in cleaned
    assert "2" not in cleaned
    assert "3" not in cleaned
    assert "4" not in cleaned
    assert "5" not in cleaned
    assert "🔧" not in cleaned
    assert "###TRANSPARENCY_LOG###" not in cleaned


def test_explicit_calculation_request_enables_tools() -> None:
    msg = "תחשב לי תזרים פרישה ותראה מספרים"
    assert allow_tools_for_intent(msg, ChatIntent.ANALYSIS) is True
