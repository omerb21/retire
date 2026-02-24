from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_report_variants_include_hebrew_verbs(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for report routing")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs):
        raise AssertionError("No tool must be executed for report routing")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)

    for msg in (
        "שלח דוח מסכם",
        "תפיק דוח",
        "הפק דוח",
        "צור report",
        "reports",
    ):
        resp = api.post(
            "/api/v1/llm/pension-chat-stream",
            json={
                "client_id": 333,
                "messages": [{"role": "user", "content": msg}],
                "pension_portfolio": [],
            },
        )
        assert resp.status_code == 200
        body = resp.text
        assert "###UI_ACTION###" in body
        assert "/clients/333/reports?auto_html=1" in body
        assert "🔧" not in body
