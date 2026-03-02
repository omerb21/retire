import pytest

from app.schemas.llm_chat import ChatMessage, ChatRequest
from app.services.intent_classifier import IntentType, classify_intent


@pytest.mark.parametrize(
    "text, expected",
    [
        ("בריאות מערכת", IntentType.SYSTEM_HEALTH),
        ("trace log 500", IntentType.SYSTEM_HEALTH),
        ("שלוף נתונים", IntentType.DATA_REQUEST),
        ("GET_CLIENT_SNAPSHOT", IntentType.DATA_REQUEST),
        ("בנה תכנית פרישה", IntentType.BUILD_TARGET_PLAN),
        ("יעד קצבה", IntentType.BUILD_TARGET_PLAN),
        ("עדכן תכנית", IntentType.ADJUST_PLAN),
        ("שנה יעד", IntentType.ADJUST_PLAN),
        ("תרחיש עזיבת עבודה", IntentType.RUN_SCENARIO),
        ("termination scenario", IntentType.RUN_SCENARIO),
        ("סימולציית מס", IntentType.TAX_SIMULATION),
        ("tax on pension", IntentType.TAX_SIMULATION),
        ("מה זה היוון?", IntentType.GENERIC_QA),
    ],
)
def test_classify_intent_smoke(text: str, expected: IntentType):
    req = ChatRequest(messages=[ChatMessage(role="user", content=text)], client_id=1)
    intent, rule_hit = classify_intent(user_message=text, request=req)
    assert intent == expected
    assert isinstance(rule_hit, str)
    assert rule_hit.strip() != ""
