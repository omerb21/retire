from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_kb_answer_matches_question_topic(monkeypatch) -> None:
    seen = {"system_text": ""}

    def fake_chat_stream(messages, client_id=None):
        # Deterministic: if the stream loop injected the conceptual alignment system message,
        # return a topic-matching answer; otherwise return an unrelated fallback.
        injected = False
        sys_lines: list[str] = []
        for m in messages or []:
            role = getattr(m, "role", None)
            content = (getattr(m, "content", "") or "").strip()
            if role == "system" and content:
                sys_lines.append(content)
            if role == "system" and "ענה רק על השאלה האחרונה של המשתמש" in content:
                injected = True
                break

        seen["system_text"] = "\n\n".join(sys_lines)

        if injected:
            yield "קיבוע זכויות הוא מונח בתחום הפרישה, והוא מתייחס להסדרה/קיבוע של הזכויות מול הרשויות בהתאם למסמכים והנתונים."
            return

        yield "קצבה היא הכנסה חודשית שוטפת לאורך זמן. הון הוא סכום שניתן למשיכה חד פעמית או למשיכות לפי צורך."

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "מה המשמעות של קיבוע זכויות"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "ענה רק על השאלה האחרונה של המשתמש" in seen["system_text"]

    assert "🔧" not in body
    assert "###TOOL_CALL###" not in body

    assert "קיבוע זכויות" in body or "161ד" in body
    assert "קצבה היא הכנסה חודשית" not in body
