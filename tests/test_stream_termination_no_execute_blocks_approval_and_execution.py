import json
from datetime import date

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop
import app.services.llm_chat.chat_stream_orchestration_parts.orchestrator_impl_parts.stream_loop as stream_loop_impl
from app.main import app
from app.models.client import Client


_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "###UI_ACTION###",
    "approval_request",
    "###TOOL_CALL###",
    "סיום עבודה – סיכום ביצוע",
    "סטטוס",
    "בוצע",
    "נוצר",
    "עודכן",
)


def _setup_client(_test_db, *, client_id: int) -> int:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1953, 4, 16),
                gender="male",
            )
            db.add(client)
            db.flush()
        persisted_id = int(getattr(client, "id", 0) or 0)
        db.commit()

    return persisted_id


def _block_tools_and_llm(monkeypatch) -> None:
    def fake_execute_tool_call(*, tool_name: str, args: dict, client_id: int, db, **kwargs) -> str:
        raise AssertionError("No tools must be executed for termination/compensation conceptual-only")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for termination/compensation conceptual-only")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

def test_stream_termination_conceptual_only_A_explainer_only(monkeypatch, _test_db) -> None:
    client_id = _setup_client(_test_db, client_id=920000010)

    def fake_today() -> date:
        return date(2026, 1, 27)

    monkeypatch.setattr(stream_loop_impl, "_today", fake_today)
    _block_tools_and_llm(monkeypatch)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": "נתחיל עם עזיבת העבודה. מה אני יכול לעשות עם הפיצויים מעסיק נוכחי? (אני מבקש להסביר את העיקרון בלבד)",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    text = resp.text
    assert "כותרת" in text
    for bad in _FORBIDDEN_SUBSTRINGS:
        assert bad not in text


def test_stream_termination_conceptual_only_B_execute_phrase_but_no_execute(monkeypatch, _test_db) -> None:
    client_id = _setup_client(_test_db, client_id=920000012)

    def fake_today() -> date:
        return date(2026, 1, 27)

    monkeypatch.setattr(stream_loop_impl, "_today", fake_today)
    _block_tools_and_llm(monkeypatch)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": "בצע עזיבת עבודה בתאריך 2025-12-31 (בלי לבצע, הסבר עקרון בלבד)",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    text = resp.text
    assert "כותרת" in text
    for bad in _FORBIDDEN_SUBSTRINGS:
        assert bad not in text
