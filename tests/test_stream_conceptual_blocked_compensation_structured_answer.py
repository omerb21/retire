from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_blocked_compensation_structured_answer(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        injected = "\n\n".join(
            str(getattr(m, "content", ""))
            for m in (messages or [])
            if getattr(m, "role", None) == "system"
        )
        assert "## blocked_compensation_in_system.md" in injected
        assert "פיצויים חסומים" in injected
        assert "כלל קשיח לשאלות מושגיות" in injected

        yield (
            "פיצויי פרישה חסומים הם רכיב שקיים בתיק אבל מסומן במערכת כלא-זמין לפעולות מסוימות עד השלמת תנאים תפעוליים.\n\n"
            "המשמעות התפעולית\n"
            "- אי אפשר לבצע פעולות מסוימות עד טיפול בחסימה\n"
            "- תוצאות עשויות להיות חלקיות אם רכיב מהותי חסום\n"
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

    assert "חסום" in body
    assert ("משמעות" in body) or ("תפעול" in body)
    assert body.count("-") >= 2
