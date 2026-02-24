import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_generate_full_report_continues_with_summary(monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_chat_stream(messages, client_id=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield '###TRANSPARENCY_LOG### {"test": true}\n###RISK_REVIEW### {"approval_required": false, "conflict_with_rag": false}\n###TOOL_CALL### {"name": "GENERATE_FULL_REPORT", "arguments": {"report_type": "full"}}'
            return
        yield "PASS - סיכום QA סופי לאחר יצירת הדוח"

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
    ) -> str:
        tool_calls.append(tool_name)
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
            "messages": [
                {
                    "role": "user",
                    "content": "אנא בצע בדיקת מערכת מקיפה (QA) והפק דוח מלא.",
                }
            ],
        },
    )

    assert response.status_code == 200

    body = response.text
    assert "###UI_ACTION###" in body
    assert "הדוח נוצר בהצלחה" in body
    assert "PASS - סיכום QA סופי לאחר יצירת הדוח" in body
    assert tool_calls == ["GENERATE_FULL_REPORT"]
