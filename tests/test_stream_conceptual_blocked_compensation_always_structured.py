from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_blocked_compensation_always_structured(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "פיצויי פרישה הם רכיב כספי שנצבר במסגרת יחסי עבודה ויכול להיות ממומש בעת סיום עבודה בהתאם לכללים. "
            "זו תשובה מושגית כללית בלבד, בלי מספרים ובלי המלצה."
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked for conceptual questions")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "מה זה פיצויים חסומים ומה המשמעות שלהם",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "🔧" not in body

    assert "כותרת:" in body
    assert ("חסומ" in body) or ("חסימה" in body)

    bullet_lines = [line for line in body.splitlines() if line.strip().startswith("-")]
    assert len(bullet_lines) >= 2
