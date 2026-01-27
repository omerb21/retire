from fastapi.testclient import TestClient

import app.services.llm_chat.chat_orchestration as non_stream_orch
from app.main import app


def test_flowA_non_stream_conceptual_only_blocks_write_tools(monkeypatch) -> None:
    def fake_run_pension_chat(*args, **kwargs):
        raise AssertionError("Non-stream orchestration must not run for conceptual-only hard stop")

    monkeypatch.setattr(non_stream_orch, "run_pension_chat", fake_run_pension_chat)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "בצע עזיבת עבודה אבל עיקרון בלבד בלי לבצע",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json().get("reply")
    assert isinstance(body, str)
    assert "###UI_ACTION###" not in body
    assert "approval_request" not in body
    assert "🔧" not in body
    assert "סיכום ביצוע" not in body
    assert "בוצע" not in body
