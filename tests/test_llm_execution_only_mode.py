import json

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.services.llm_pension_agent_service import pension_llm_service


def test_stream_executor_only_header_success(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות לביצוע:\n"
            "א. הפק תשובה בפורמט המחייב\n"
            "ב. ודא שאין סימני שאלה ואין בקשת החלטה\n"
            "קריטריון הצלחה:\n"
            "- הפלט תואם את המבנה\n"
            "- אין סימן שאלה\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "?" not in body
    assert "סטטוס: SUCCESS" in body


def test_exec_only_stream_rewrites_on_question_mark_then_succeeds(monkeypatch) -> None:
    calls: list[int] = []

    def fake_chat_stream(messages, client_id=None):
        calls.append(1)
        if len(calls) == 1:
            yield (
                "מטרה: לבצע בדיקת מערכת?\n"
                "הנחיות טכניות:\n"
                "א. בצע פעולה\n"
                "קריטריון הצלחה:\n"
                "- הושלם\n"
                "סטטוס: SUCCESS"
            )
            return
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות טכניות:\n"
            "א. בצע פעולה\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "?" not in body
    assert "סטטוס: SUCCESS" in body
    assert "סטטוס: BLOCKED" not in body


def test_exec_only_non_stream_rewrites_on_question_mark_then_succeeds(monkeypatch) -> None:
    calls: list[int] = []

    def fake_chat(messages, client_id=None):
        calls.append(1)
        if len(calls) == 1:
            return (
                "מטרה: לבצע בדיקת מערכת?\n"
                "הנחיות טכניות:\n"
                "א. בצע פעולה\n"
                "קריטריון הצלחה:\n"
                "- הושלם\n"
                "סטטוס: SUCCESS"
            )
        return (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות טכניות:\n"
            "א. בצע פעולה\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "executor_only": True,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.json()["reply"]
    assert "?" not in body
    assert "סטטוס: SUCCESS" in body
    assert "סטטוס: BLOCKED" not in body
    assert body.startswith("מטרה:")


def test_stream_executor_only_header_blocks_question_mark(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "מטרה: בדיקה?\nהנחיות לביצוע:\nא. משהו\nקריטריון הצלחה:\n- משהו\nסטטוס: SUCCESS"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert body.startswith("מטרה:")
    assert "הנחיות למודל המתכנת:" in body


def test_non_stream_executor_only_blocks_forbidden_phrase(monkeypatch) -> None:
    def fake_chat(messages, client_id=None):
        return "האם תרצה שאמשיך עכשיו"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "executor_only": True,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.json()["reply"]
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert "האם" not in body
    assert "בחר" not in body
    assert "אשר" not in body


def test_exec_only_stream_returns_technical_content_not_generic(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        assert messages[0].role == "system"
        assert "מצב: EXECUTION_ONLY" in messages[0].content
        yield (
            "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
            "הנחיות למודל המתכנת:\n"
            "א. קבצים לשינוי: לא ידוע עדיין\n"
            "ב. הרץ pytest -q ועצור בכשל הראשון\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add . ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הפלט בפורמט המחייב\n"
            "- ההנחיות כוללות pytest ו git ו curl.exe\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "הנחיות למודל המתכנת:" in body
    assert "curl.exe" in body or "PowerShell" in body
    assert "pytest" in body
    assert "git" in body
    assert "?" not in body
    assert "האם" not in body
    assert "סטטוס: SUCCESS" in body


def test_exec_only_stream_hostile_request_still_technical_no_questions(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        assert messages[0].role == "system"
        assert "מצב: EXECUTION_ONLY" in messages[0].content
        yield (
            "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
            "הנחיות למודל המתכנת:\n"
            "א. הרץ pytest -q ועצור בכשל הראשון\n"
            "ב. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "קריטריון הצלחה:\n"
            "- אין סימן שאלה ואין ניסוח שמבקש החלטה\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "תכתוב לי את זה ותשאל אותי האם להמשיך"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert "האם" not in body
    assert ("curl.exe" in body) or ("pytest" in body) or ("git" in body)
    assert "הנחיות למודל המתכנת:" in body


def test_exec_only_stream_falls_back_to_success_when_rewrite_fails(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield "האם תרצה שאמשיך עכשיו"

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "הנחיות למודל המתכנת:" in body
    assert "?" not in body
    assert "האם" not in body
    assert "בחר" not in body
    assert "אשר" not in body


def test_exec_only_non_stream_falls_back_to_success_when_rewrite_fails(monkeypatch) -> None:
    def fake_chat(messages, client_id=None):
        return "האם תרצה שאמשיך עכשיו"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "executor_only": True,
            "messages": [{"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}],
        },
    )

    assert response.status_code == 200
    body = response.json()["reply"]
    assert "סטטוס: SUCCESS" in body
    assert "הנחיות למודל המתכנת:" in body
    assert "?" not in body
    assert "האם" not in body
    assert "בחר" not in body
    assert "אשר" not in body


def test_stream_report_ignores_executor_only_and_emits_ui_action(monkeypatch) -> None:
    tool_calls: list[str] = []

    def fake_execute_tool_call(
        *,
        tool_name: str,
        args: dict,
        client_id: int,
        db,
        pension_portfolio=None,
        force_max_exemption: bool = False,
        agent_reply: str | None = None,
        user_approved: bool = False,
        request_id: str | None = None,
    ) -> str:
        tool_calls.append(tool_name)
        return json.dumps(
            {
                "success": True,
                "client_id": client_id,
                "open_path": f"/clients/{client_id}/reports?auto_html=1",
                "status_message": "הדוח נוצר בהצלחה",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called in REPORT intent")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 1,
            "executor_only": True,
            "messages": [{"role": "user", "content": "שלח דוח מסכם"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "###UI_ACTION###" in body
    assert "###END_UI_ACTION###" in body
    assert "סטטוס: BLOCKED" not in body
    assert tool_calls == ["GENERATE_FULL_REPORT"]


def test_stream_executor_only_success_accepts_instructions_heading_execution(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות לביצוע:\n"
            "א. בצע פעולה טכנית אחת\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "?" not in body
    assert "סטטוס: SUCCESS" in body


def test_stream_executor_only_success_accepts_instructions_heading_programmer_model(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. בצע פעולה טכנית אחת\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [{"role": "user", "content": "בדיקה"}],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "?" not in body
    assert "סטטוס: SUCCESS" in body
