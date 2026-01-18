from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_fixation_documents_structured(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        injected = "\n\n".join(
            str(getattr(m, "content", ""))
            for m in (messages or [])
            if getattr(m, "role", None) == "system"
        )
        assert "## fixation_documents_checklist.md" in injected
        assert "מסמכים נפוצים בקיבוע זכויות" in injected
        assert "כלל קשיח לשאלות מושגיות" in injected

        yield (
            "מסמכים נפוצים בקיבוע זכויות\n\n"
            "מסמכי זיהוי\n"
            "- תעודת זהות\n"
            "- פרטי קשר מעודכנים\n\n"
            "מסמכי מעסיק וסיום עבודה\n"
            "- מכתב סיום עבודה\n\n"
            "מסמכי קופות\n"
            "- דוחות יתרות\n"
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

    assert "מסמכים" in body
    assert "קיבוע זכויות" in body

    assert body.count("-") >= 3
    assert "מעסיק" in body
    assert "קופות" in body
