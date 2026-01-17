import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_conceptual_form_question_no_ui_action(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "טופס 161ד הוא טופס רשות המסים שקשור להסדרה של קיבוע זכויות בהקשר פרישה."

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 36,
            "messages": [
                {
                    "role": "user",
                    "content": "בקיבוע זכויות, מה התפקיד של טופס 161ד?",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" not in body
    assert "/api/v1/fixation/" not in body
    assert "package" not in body
    assert "🔧" not in body
    assert "###TOOL_CALL###" not in body

    assert ("161ד" in body) or ("טופס" in body) or ("רשות המסים" in body)


def test_stream_report_still_returns_ui_action(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield '###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {"report_type": "full"}}'
        return

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        if tool_name == "GENERATE_FULL_REPORT":
            return json.dumps(
                {
                    "success": True,
                    "client_id": client_id,
                    "open_path": f"/clients/{client_id}/reports?auto_html=1",
                    "status_message": "הדוח נוצר בהצלחה",
                },
                ensure_ascii=False,
            )
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "שלח דוח מסכם"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "###UI_ACTION###" in body
    assert "הדוח נוצר בהצלחה" in body
