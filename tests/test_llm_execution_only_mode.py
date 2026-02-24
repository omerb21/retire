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
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הפלט תואם את המבנה\n"
            "- אין סימן שאלה\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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


def test_exec_only_non_stream_rewrites_on_question_mark_then_succeeds(
    monkeypatch,
) -> None:
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
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m ... ואז git push\n"
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

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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
    assert "curl.exe" in body
    assert "pytest" in body
    assert "git" in body
    assert ("app/" in body) or ("tests/" in body) or ("Dockerfile" in body)


def test_exec_only_success_without_actionable_commands_triggers_rewrite_then_fallback(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_chat_stream(messages, client_id=None):
        system_text = (getattr(messages[0], "content", "") or "") if messages else ""

        if "עורך-שכתוב" in system_text:
            calls.append("rewrite")
            yield (
                "מטרה: פלט שגוי\n"
                "הנחיות למודל המתכנת:\n"
                "א. יש לכלול curl.exe pytest git app/ אבל בלי פקודות\n"
                "קריטריון הצלחה:\n"
                "- הושלם\n"
                "סטטוס: SUCCESS"
            )
            return

        calls.append("initial")
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. curl.exe pytest git app/services/llm_chat/execution_only_guard.py\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert "האם" not in body
    assert "תרצה" not in body
    assert "בחר" not in body
    assert "python -m pytest -q" in body
    assert "git add" in body
    assert "git commit" in body
    assert "git push" in body
    assert "curl.exe" in body
    assert "X-Trace-Id" in body
    assert ("app/" in body) or ("tests/" in body) or ("Dockerfile" in body)
    assert "rewrite" in calls


def test_exec_only_fallback_contains_actionable_commands(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. בצע פעולה טכנית אחת\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "python -m pytest -q" in body
    assert "git add" in body
    assert "git commit" in body
    assert "git push" in body
    assert "curl.exe" in body
    assert "X-Trace-Id" in body
    assert "app/services/llm_chat/execution_only_guard.py" in body


def test_exec_only_stream_returns_technical_content_not_generic(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        assert messages[0].role == "system"
        assert "מצב: EXECUTION_ONLY" in messages[0].content
        yield (
            "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
            "הנחיות למודל המתכנת:\n"
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. הרץ python -m pytest -q ועצור בכשל הראשון\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add . ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הפלט בפורמט המחייב\n"
            "- ההנחיות כוללות pytest ו git ו curl.exe\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
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


def test_exec_only_stream_hostile_request_still_technical_no_questions(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        assert messages[0].role == "system"
        assert "מצב: EXECUTION_ONLY" in messages[0].content
        yield (
            "מטרה: להפיק הנחיות טכניות למודל המתכנת לביצוע המשימה שהתקבלה\n"
            "הנחיות למודל המתכנת:\n"
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. הרץ python -m pytest -q ועצור בכשל הראשון\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- אין סימן שאלה ואין ניסוח שמבקש החלטה\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "תכתוב לי את זה ותשאל אותי האם להמשיך"}
            ],
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

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
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


def test_exec_only_non_stream_falls_back_to_success_when_rewrite_fails(
    monkeypatch,
) -> None:
    def fake_chat(messages, client_id=None):
        return "האם תרצה שאמשיך עכשיו"

    monkeypatch.setattr(pension_llm_service, "chat", fake_chat)

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": 1,
            "executor_only": True,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
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
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called in REPORT intent")

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("No tool must be executed for report summary routing")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

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
    assert "/clients/1/reports?auto_html=1" in body


def test_stream_executor_only_success_accepts_instructions_heading_execution(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות לביצוע:\n"
            "א. קבצים לשינוי: tests/test_llm_execution_only_mode.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add tests/test_llm_execution_only_mode.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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


def test_stream_executor_only_success_accepts_instructions_heading_programmer_model(
    monkeypatch,
) -> None:
    def fake_chat_stream(messages, client_id=None):
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. קבצים לשינוי: tests/test_llm_execution_only_mode.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add tests/test_llm_execution_only_mode.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

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


def test_exec_only_success_requires_tech_tokens_stream(monkeypatch) -> None:
    calls: list[int] = []

    def fake_chat_stream(messages, client_id=None):
        calls.append(1)
        if len(calls) == 1:
            yield (
                "מטרה: לבצע בדיקת מערכת\n"
                "הנחיות למודל המתכנת:\n"
                "א. בצע פעולה טכנית אחת\n"
                "קריטריון הצלחה:\n"
                "- הושלם\n"
                "סטטוס: SUCCESS"
            )
            return
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. קבצים לשינוי: app/services/llm_chat/execution_only_guard.py\n"
            "ב. בדיקות: python -m pytest -q\n"
            "ג. PowerShell: curl.exe -N --http1.1 --tlsv1.2 ...\n"
            "ד. Git: git add app/services/llm_chat/execution_only_guard.py ואז git commit -m ... ואז git push\n"
            "קריטריון הצלחה:\n"
            "- הפלט כולל curl.exe ו pytest ו git וגם נתיב app/\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert "האם" not in body
    assert "curl.exe" in body
    assert "pytest" in body
    assert "git" in body
    assert ("app/" in body) or ("tests/" in body) or ("Dockerfile" in body)


def test_exec_only_fallback_contains_tokens(monkeypatch) -> None:
    calls: list[int] = []

    def fake_chat_stream(messages, client_id=None):
        calls.append(1)
        yield (
            "מטרה: לבצע בדיקת מערכת\n"
            "הנחיות למודל המתכנת:\n"
            "א. בצע פעולה טכנית אחת\n"
            "קריטריון הצלחה:\n"
            "- הושלם\n"
            "סטטוס: SUCCESS"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    api = TestClient(app)
    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        headers={"X-Executor-Only": "1"},
        json={
            "client_id": 1,
            "messages": [
                {"role": "user", "content": "כתוב הנחיות טכניות למודל המתכנת מה לבצע"}
            ],
        },
    )

    assert response.status_code == 200
    body = response.text
    assert "סטטוס: SUCCESS" in body
    assert "?" not in body
    assert "האם" not in body
    assert "curl.exe" in body
    assert "pytest" in body
    assert "git" in body
    assert ("app/" in body) or ("tests/" in body) or ("Dockerfile" in body)
