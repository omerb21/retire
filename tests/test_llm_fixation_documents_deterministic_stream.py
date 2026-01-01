import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def test_stream_fixation_documents_request_is_deterministic(monkeypatch) -> None:
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
        assert tool_name == "GENERATE_TAX_DEDUCTION_DOCUMENTS"
        assert args.get("document_type") == "fixation_package"
        return json.dumps(
            {
                "success": True,
                "client_id": client_id,
                "download_url": f"/api/v1/fixation/{client_id}/package",
                "status_message": "המסמך הופק בהצלחה",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "messages": [
                {
                    "role": "user",
                    "content": "שלח לי את מסמכי קיבוע הזכויות",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "/api/v1/fixation/1/package" in body
    assert tool_calls == ["GENERATE_TAX_DEDUCTION_DOCUMENTS"]
