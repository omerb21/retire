from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_words_only_report_explainer_always_structured(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "קיבלתי. אפשר להמשיך בהסבר מילולי בלבד על בסיס הנתונים שנשלחו.\n"
            "בתיק שלך יש פיצויים צבורים.\n"
            "פיצויים מסומן כחסום.\n"
            "צריך להחליט צעדים אופרטיביים.\n"
            "יעד מול עודף 12.\n"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("execute_tool_call must not be invoked for conceptual questions")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    user_messages = [
        "הסבר במילים בלבד מה אומר הדוח ומה המשמעות, בלי מספרים",
        "פרש במילים את הדוח: מה זה ברוטו, מה זה נטו, ומה משמעות יעד מול עודף, בלי מספרים",
        "תסביר את הדוח במילים לילד בן 12, בלי מספרים",
    ]

    for user_message in user_messages:
        response = api.post(
            "/api/v1/llm/pension-chat-stream",
            json={
                "client_id": 1,
                "messages": [
                    {
                        "role": "user",
                        "content": user_message,
                    }
                ],
            },
        )

        assert response.status_code == 200
        body = response.text

        assert "###UI_ACTION###" not in body
        assert "🔧" not in body

        assert "כותרת:" in body
        assert "א." in body
        assert "ב." in body
        assert "ג." in body
        assert "ד." in body

        assert "קיבלתי. אפשר להמשיך" not in body
        assert "בתיק שלך" not in body

        assert not any(ch.isdigit() for ch in body)
