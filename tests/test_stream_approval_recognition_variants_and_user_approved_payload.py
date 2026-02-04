import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app
from app.models.client import Client
from app.models.scenario import Scenario
from app.services.llm_chat.pending_approvals import store_pending_approval_ui_action
from app.services.llm_chat.chat_orchestration_helpers import store_pending_approval_request
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    store_current_employer_termination_plan_preview,
)


def test_stream_text_approval_variant_with_pending_executes(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000002).first()
        if client is None:
            client = Client(
                id=920000002,
                id_number_raw="920000002",
                id_number="920000002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        tool_args = {"accounts": [], "use_provided_accounts_only": True}
        db.add(
            Scenario(
                client_id=client_id,
                scenario_name="pending_approval",
                apply_tax_planning=False,
                apply_capitalization=False,
                apply_exemption_shield=False,
                parameters=json.dumps(
                    {"tool_name": "TRANSFORM_FUNDS_TO_ASSETS", "arguments": tool_args},
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for text approval")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, user_approved: bool = False, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "כן, מאשר."}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", {"accounts": [], "use_provided_accounts_only": True})]
    assert "אין בקשת אישור פתוחה" not in resp.text


def test_stream_text_approval_variant_without_pending_refuses(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for text approval")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed without pending approval")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 930000001,
            "messages": [{"role": "user", "content": "מאשר!"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "לא נמצאה בקשת אישור פעילה" in body
    assert "🔧" not in body


def test_stream_user_approved_json_with_pending_executes(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 920000003).first()
        if client is None:
            client = Client(
                id=920000003,
                id_number_raw="920000003",
                id_number="920000003",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        stored_args = {
            "accounts": [{"account_id": "A", "amount": 1}],
            "use_provided_accounts_only": True,
        }
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=stored_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, user_approved: bool = False, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': stored_args}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", stored_args)]
    assert "🔧" in resp.text


def test_stream_user_approved_json_without_pending_allowlisted_executes(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, user_approved: bool = False, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "TRANSFORM_FUNDS_TO_ASSETS"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    approved_args = {"accounts": [], "use_provided_accounts_only": True}
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 940000001,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': approved_args}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert tool_calls == []
    body = resp.text
    assert "אין בקשת אישור פתוחה תואמת" in body
    assert "🔧" not in body


def test_stream_user_approved_json_without_pending_non_allowlisted_refuses(monkeypatch) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed without pending approval")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": 950000001,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'EXECUTE_RETIREMENT_SCENARIO', 'arguments': {}}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "אין בקשת אישור פתוחה תואמת" in body
    assert "🔧" not in body


def test_stream_user_approved_json_dedupe_prevents_reexecution(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, user_approved: bool = False, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    api = TestClient(app)
    client_id = 960000001
    approved_args = {"accounts": [], "use_provided_accounts_only": True}
    payload = f"###USER_APPROVED### {json.dumps({'tool_name': 'TRANSFORM_FUNDS_TO_ASSETS', 'arguments': approved_args}, ensure_ascii=False)}"

    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        store_ok = store_pending_approval_ui_action(
            db=db,
            client_id=client_id,
            request_kind="execute_target_plan",
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            tool_args=approved_args,
            ui_action="dummy",
        )
        assert store_ok is True
        db.commit()

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": payload}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "🔧" in resp1.text

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": payload}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "אין בקשת אישור פתוחה תואמת" in resp2.text
    assert "🔧" not in resp2.text

    assert tool_calls == [("TRANSFORM_FUNDS_TO_ASSETS", approved_args)]


def _ensure_client(Session, *, client_id: int) -> None:
    with Session() as db:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is None:
            client = Client(
                id=client_id,
                id_number_raw=str(client_id),
                id_number=str(client_id),
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        db.commit()


def test_stream_process_termination_user_approved_missing_nonce_blocks(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    client_id = 970000001
    _ensure_client(Session, client_id=client_id)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed when approval nonce is missing")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    preview_id = "preview-970000001"
    with Session() as db:
        store_current_employer_termination_plan_preview(
            db=db,
            client_id=client_id,
            payload={
                "termination_arguments_template": {"confirmed": True},
                "awaiting_user_confirmation": False,
                "approved": True,
                "declined": False,
                "preview_id": preview_id,
                "used": False,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            },
        )
        store_pending_approval_request(
            db=db,
            client_id=client_id,
            tool_name="PROCESS_TERMINATION",
            tool_args={"confirmed": True},
        )
        db.commit()

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'PROCESS_TERMINATION', 'arguments': {}}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "לאשר את תכנית ברירת המחדל" in resp.text
    assert "🔧" not in resp.text


def test_stream_process_termination_user_approved_wrong_approval_id_blocks(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]
    client_id = 970000002
    _ensure_client(Session, client_id=client_id)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    def fake_execute_tool_call(*args, **kwargs) -> str:
        raise AssertionError("Tool must not be executed when approval_id mismatches")

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    preview_id = "preview-970000002"
    with Session() as db:
        store_current_employer_termination_plan_preview(
            db=db,
            client_id=client_id,
            payload={
                "termination_arguments_template": {"confirmed": True},
                "awaiting_user_confirmation": False,
                "approved": True,
                "declined": False,
                "preview_id": preview_id,
                "used": False,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            },
        )
        store_pending_approval_request(
            db=db,
            client_id=client_id,
            tool_name="PROCESS_TERMINATION",
            tool_args={"confirmed": True},
        )
        db.commit()

    with Session() as db:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert row is not None
        parsed = json.loads(row.parameters)
        stored_args = parsed.get("arguments")
        assert isinstance(stored_args, dict)
        stored_approval_id = stored_args.get("approval_id")
        assert isinstance(stored_approval_id, str) and stored_approval_id

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [
                {
                    "role": "user",
                    "content": f"###USER_APPROVED### {json.dumps({'tool_name': 'PROCESS_TERMINATION', 'arguments': {'approval_id': 'WRONG', 'preview_id': preview_id}}, ensure_ascii=False)}",
                }
            ],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    assert "לאשר את תכנית ברירת המחדל" in resp.text
    assert "🔧" not in resp.text


def test_stream_process_termination_user_approved_success_consumes_preview_and_blocks_reuse(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]
    client_id = 970000003
    _ensure_client(Session, client_id=client_id)

    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called when user approval marker is present")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    tool_calls: list[tuple[str, dict]] = []

    def fake_execute_tool_call(*, tool_name: str, args: dict, user_approved: bool = False, **kwargs) -> str:
        tool_calls.append((tool_name, args))
        assert tool_name == "PROCESS_TERMINATION"
        assert user_approved is True
        return json.dumps({"success": True}, ensure_ascii=False)

    monkeypatch.setattr(stream_orch, "execute_tool_call", fake_execute_tool_call)

    preview_id = "preview-970000003"
    with Session() as db:
        store_current_employer_termination_plan_preview(
            db=db,
            client_id=client_id,
            payload={
                "termination_arguments_template": {"confirmed": True},
                "awaiting_user_confirmation": False,
                "approved": True,
                "declined": False,
                "preview_id": preview_id,
                "used": False,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            },
        )
        store_pending_approval_request(
            db=db,
            client_id=client_id,
            tool_name="PROCESS_TERMINATION",
            tool_args={"confirmed": True},
        )
        db.commit()

    with Session() as db:
        row = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "pending_approval")
            .order_by(Scenario.created_at.desc())
            .first()
        )
        assert row is not None
        parsed = json.loads(row.parameters)
        stored_args = parsed.get("arguments")
        assert isinstance(stored_args, dict)
        stored_approval_id = stored_args.get("approval_id")
        assert isinstance(stored_approval_id, str) and stored_approval_id

    api = TestClient(app)
    payload = f"###USER_APPROVED### {json.dumps({'tool_name': 'PROCESS_TERMINATION', 'arguments': {'approval_id': stored_approval_id, 'preview_id': preview_id}}, ensure_ascii=False)}"

    resp1 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": payload}],
            "pension_portfolio": [],
        },
    )
    assert resp1.status_code == 200
    assert "🔧" in resp1.text
    assert tool_calls == [("PROCESS_TERMINATION", {"confirmed": True, "approval_id": stored_approval_id, "preview_id": preview_id})]

    resp2 = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": payload}],
            "pension_portfolio": [],
        },
    )
    assert resp2.status_code == 200
    assert "🔧" not in resp2.text
    assert "לאשר את תכנית ברירת המחדל" in resp2.text
