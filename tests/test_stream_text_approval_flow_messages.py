from fastapi.testclient import TestClient

from app.main import app


def test_stream_no_pending_approval_message_is_locked() -> None:
    api = TestClient(app)

    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 12345,
            "messages": [{"role": "user", "content": "מאשר"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    assert "לא נמצאה בקשת אישור פעילה." in body
    assert "אין בקשת אישור פתוחה" not in body
