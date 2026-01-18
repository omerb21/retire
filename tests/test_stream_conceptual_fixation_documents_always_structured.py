from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_fixation_documents_always_structured(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "קיבוע זכויות הוא תהליך מול רשות המסים שמסדיר את אופן מימוש הזכויות שנצברו בפרישה. "
            "בדרך כלל יש צורך לאסוף מסמכים ולוודא עקביות בין הגופים המעורבים."
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
                    "content": "איזה מסמכים בדרך כלל מגישים בקיבוע זכויות",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "🔧" not in body

    assert "כותרת: מסמכים לקיבוע זכויות" in body

    bullet_lines = [line for line in body.splitlines() if line.strip().startswith("-")]
    assert len(bullet_lines) >= 8
