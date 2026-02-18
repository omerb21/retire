from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.services.llm_chat.chat_orchestration as orch
import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.tool_execution as tool_exec
from app.main import app
from app.models.client import Client
from app.models.current_employment.employer import CurrentEmployer
from app.models.scenario import Scenario
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    store_current_employer_termination_plan_preview,
)
from app.services.snapshot_service import SnapshotService
from app.services.agent_execution import execute_agent_request as exec_entry_mod
from app.services.agent_execution import tool_executor as tool_exec_mod


def _install_trace_capture(monkeypatch) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []

    def fake_log_trace_event(*, event_type: str, payload=None, **kwargs):
        events.append((event_type, payload))

    monkeypatch.setattr(exec_entry_mod, "log_trace_event", fake_log_trace_event)
    monkeypatch.setattr(tool_exec_mod, "log_trace_event", fake_log_trace_event)
    return events


def _assert_trace_invariants(
    events: list[tuple[str, Any]],
    *,
    expected_execution_mode: str,
    expect_tool_calls: bool,
) -> None:
    types = [t for (t, _p) in events]

    assert "user_input" in types
    assert "execution_mode" in types
    assert "final_response" in types

    exec_payloads = [p for (t, p) in events if t == "execution_mode"]
    assert exec_payloads
    assert exec_payloads[0].get("execution_mode") == expected_execution_mode

    tool_call_indices = [i for i, (t, _p) in enumerate(events) if t == "tool_call"]
    tool_result_indices = [i for i, (t, _p) in enumerate(events) if t == "tool_result"]

    if expect_tool_calls:
        assert tool_call_indices

    if tool_call_indices:
        assert len(tool_call_indices) == len(tool_result_indices)
        for call_i, res_i in zip(tool_call_indices, tool_result_indices):
            assert res_i > call_i


def _seed_client(*, db, client_id: int) -> None:
    row = db.query(Client).filter(Client.id == client_id).first()
    if row is None:
        row = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Test User",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
        )
        db.add(row)
        db.flush()


def _seed_pending_approval(*, db, client_id: int, tool_name: str, arguments: dict) -> None:
    db.query(Scenario).filter(Scenario.client_id == client_id).filter(
        Scenario.scenario_name == "pending_approval"
    ).delete(synchronize_session=False)
    db.flush()
    db.add(
        Scenario(
            client_id=client_id,
            scenario_name="pending_approval",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps({"tool_name": tool_name, "arguments": arguments}, ensure_ascii=False),
        )
    )
    db.commit()


def _clear_undo_snapshot(*, db, client_id: int) -> None:
    db.query(Scenario).filter(Scenario.client_id == client_id).filter(
        Scenario.scenario_name == "undo_snapshot"
    ).delete(synchronize_session=False)
    db.commit()


def _get_pending_approval_row(*, db, client_id: int):
    return (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pending_approval")
        .order_by(Scenario.created_at.desc())
        .first()
    )


def _get_latest_undo_snapshot_row(*, db, client_id: int):
    return (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "undo_snapshot")
        .order_by(Scenario.created_at.desc(), Scenario.id.desc())
        .first()
    )


def _extract_ui_action_payload(body: str) -> dict:
    assert "###UI_ACTION###" in body
    payload_json = body.split("###UI_ACTION###", 1)[1].split("###END_UI_ACTION###", 1)[0]
    return json.loads(payload_json)


@pytest.mark.parametrize("streaming", [False, True])
def test_stage9_scenario_a_preview_readonly(monkeypatch, _test_db, streaming: bool) -> None:
    Session = _test_db["Session"]
    client_id = 991000001

    with Session() as db:
        _seed_client(db=db, client_id=client_id)
        db.commit()

    events = _install_trace_capture(monkeypatch)

    api = TestClient(app)
    endpoint = "/api/v1/llm/pension-chat-stream" if streaming else "/api/v1/llm/pension-chat"
    resp = api.post(
        endpoint,
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "GET_CLIENT_SNAPSHOT"}],
        },
    )
    assert resp.status_code == 200

    raw = resp.text if streaming else resp.json().get("reply")
    parsed = json.loads(raw)

    assert parsed.get("success") is True
    assert parsed.get("tool_name") == "GET_CLIENT_SNAPSHOT"
    assert isinstance(parsed.get("total_items"), int)
    breakdown = parsed.get("breakdown")
    assert isinstance(breakdown, dict)
    assert "pension_funds" in breakdown
    assert "capital_assets" in breakdown

    _assert_trace_invariants(events, expected_execution_mode="agent_mode", expect_tool_calls=True)


@pytest.mark.parametrize("streaming", [False, True])
def test_stage9_scenario_b_approval_write_flow(monkeypatch, _test_db, streaming: bool) -> None:
    Session = _test_db["Session"]
    client_id = 991000002

    def _no_llm(*args, **kwargs):
        raise AssertionError("LLM must not be called for deterministic approval execution")

    monkeypatch.setattr(orch.pension_llm_service, "chat", _no_llm)
    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", _no_llm)

    def fake_save_snapshot(self, client_id: int, snapshot_name: str = None):
        return {
            "snapshot": {
                "data": {
                    "pension_funds": [],
                    "capital_assets": [],
                    "additional_incomes": [],
                    "current_employer": None,
                    "grants": [],
                    "legacy_grants": [],
                    "termination_event": None,
                    "fixation_result": None,
                }
            },
            "total_items": 0,
            "success": True,
        }

    monkeypatch.setattr(SnapshotService, "save_snapshot", fake_save_snapshot)

    def fake_transform(*, args: dict, client_id: int, db, agent_tools=None, **kwargs) -> str:
        return json.dumps(
            {
                "success": True,
                "total_converted": 1,
                "converted_pensions": 1,
                "converted_capitals": 0,
                "converted_commutations": 0,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(tool_exec, "handle_transform_funds_to_assets", fake_transform)

    with Session() as db:
        _seed_client(db=db, client_id=client_id)
        _clear_undo_snapshot(db=db, client_id=client_id)
        _seed_pending_approval(
            db=db,
            client_id=client_id,
            tool_name="TRANSFORM_FUNDS_TO_ASSETS",
            arguments={"accounts": [], "use_provided_accounts_only": True},
        )

    events = _install_trace_capture(monkeypatch)

    api = TestClient(app)
    endpoint = "/api/v1/llm/pension-chat-stream" if streaming else "/api/v1/llm/pension-chat"
    resp = api.post(
        endpoint,
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200

    with Session() as db:
        pending = _get_pending_approval_row(db=db, client_id=client_id)
        assert pending is None

        undo_row = _get_latest_undo_snapshot_row(db=db, client_id=client_id)
        assert undo_row is not None

    _assert_trace_invariants(events, expected_execution_mode="agent_mode", expect_tool_calls=True)


@pytest.mark.parametrize("streaming", [False, True])
def test_stage9_scenario_c_termination_with_severance(monkeypatch, _test_db, streaming: bool) -> None:
    Session = _test_db["Session"]
    client_id = 991000003

    def _no_llm(*args, **kwargs):
        raise AssertionError("LLM must not be called for deterministic approval execution")

    monkeypatch.setattr(orch.pension_llm_service, "chat", _no_llm)
    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", _no_llm)

    termination_date_str = "2025-01-01"
    initial_severance: float

    def fake_process_termination(*, args: dict, client_id: int, db, **kwargs) -> str:
        termination_date_raw = (args or {}).get("termination_date")
        termination_date = None
        try:
            if isinstance(termination_date_raw, str) and termination_date_raw.strip():
                termination_date = date.fromisoformat(termination_date_raw.strip())
        except Exception:
            termination_date = None
        if termination_date is None:
            termination_date = date(2025, 1, 1)

        employer = db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).first()
        assert employer is not None

        employer.end_date = termination_date
        db.commit()

        return json.dumps(
            {
                "success": True,
                "tool_name": "PROCESS_TERMINATION",
                "termination_date": termination_date.isoformat(),
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(tool_exec, "handle_process_termination", fake_process_termination)

    with Session() as db:
        _seed_client(db=db, client_id=client_id)

        db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).delete(
            synchronize_session=False
        )
        db.flush()
        db.add(
            CurrentEmployer(
                client_id=client_id,
                employer_name="Test Employer",
                start_date=date(2020, 1, 1),
                end_date=None,
                severance_accrued=50000.0,
                last_salary=10000.0,
            )
        )
        db.flush()
        db.commit()

    with Session() as db:
        reloaded_employer = (
            db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).order_by(CurrentEmployer.id.desc()).first()
        )
        assert reloaded_employer is not None
        initial_severance = float(getattr(reloaded_employer, "severance_accrued", 0) or 0)

    with Session() as db:
        store_current_employer_termination_plan_preview(
            db=db,
            client_id=client_id,
            payload={
                "plan_args": {},
                "termination_arguments_template": {
                    "confirmed": True,
                    "termination_date": termination_date_str,
                    "exempt_choice": "redeem_with_exemption",
                    "taxable_choice": "annuity",
                },
                "awaiting_user_confirmation": False,
                "approved": True,
                "declined": False,
                "preview_id": "stage9-preview",
            },
        )
        db.commit()

        _seed_pending_approval(
            db=db,
            client_id=client_id,
            tool_name="PROCESS_TERMINATION",
            arguments={
                "confirmed": True,
                "termination_date": termination_date_str,
                "exempt_choice": "redeem_with_exemption",
                "taxable_choice": "annuity",
            },
        )

    events = _install_trace_capture(monkeypatch)

    api = TestClient(app)
    endpoint = "/api/v1/llm/pension-chat-stream" if streaming else "/api/v1/llm/pension-chat"
    resp = api.post(
        endpoint,
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "מאשר"}],
            "pension_portfolio": [],
        },
    )
    assert resp.status_code == 200

    with Session() as db:
        pending = _get_pending_approval_row(db=db, client_id=client_id)
        assert pending is None

        reloaded_employer = (
            db.query(CurrentEmployer).filter(CurrentEmployer.client_id == client_id).order_by(CurrentEmployer.id.desc()).first()
        )
        assert reloaded_employer is not None

        assert reloaded_employer.end_date is not None
        assert reloaded_employer.end_date.isoformat() == termination_date_str

        assert float(getattr(reloaded_employer, "severance_accrued", 0) or 0) == initial_severance
        if initial_severance > 0:
            assert float(getattr(reloaded_employer, "severance_accrued", 0) or 0) != 0.0

    _assert_trace_invariants(events, expected_execution_mode="agent_mode", expect_tool_calls=True)


@pytest.mark.parametrize("streaming", [False, True])
def test_stage9_scenario_d_undo_restore_flow(monkeypatch, _test_db, streaming: bool) -> None:
    Session = _test_db["Session"]
    client_id = 991000004

    def _no_llm(*args, **kwargs):
        raise AssertionError("LLM must not be called for undo deterministic flow")

    monkeypatch.setattr(orch.pension_llm_service, "chat", _no_llm)
    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", _no_llm)

    def fake_restore_snapshot(self, client_id: int, snapshot_data: dict):
        return {"success": True, "message": "restored"}

    monkeypatch.setattr(SnapshotService, "restore_snapshot", fake_restore_snapshot)

    with Session() as db:
        _seed_client(db=db, client_id=client_id)

        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "undo_snapshot"
        ).delete(synchronize_session=False)
        db.query(Scenario).filter(Scenario.client_id == client_id).filter(
            Scenario.scenario_name == "pending_approval"
        ).delete(synchronize_session=False)
        db.flush()

        undo = Scenario(
            client_id=client_id,
            scenario_name="undo_snapshot",
            apply_tax_planning=False,
            apply_capitalization=False,
            apply_exemption_shield=False,
            parameters=json.dumps(
                {
                    "snapshot": {
                        "data": {
                            "pension_funds": [],
                            "capital_assets": [],
                            "additional_incomes": [],
                            "current_employer": None,
                            "grants": [],
                            "legacy_grants": [],
                            "termination_event": None,
                            "fixation_result": None,
                        }
                    }
                },
                ensure_ascii=False,
            ),
            created_at=datetime.now(timezone.utc),
        )
        db.add(undo)
        db.commit()
        undo_id = int(getattr(undo, "id", 0) or 0)
        assert undo_id > 0

    api = TestClient(app)
    events_1 = _install_trace_capture(monkeypatch)

    endpoint = "/api/v1/llm/pension-chat-stream" if streaming else "/api/v1/llm/pension-chat"
    resp1 = api.post(
        endpoint,
        json={"client_id": client_id, "messages": [{"role": "user", "content": "undo"}]},
    )
    assert resp1.status_code == 200

    body1 = resp1.text if streaming else resp1.json().get("reply")
    ui_payload = _extract_ui_action_payload(body1)
    assert ui_payload.get("actions")[0].get("tool_name") == "RESTORE_SYSTEM_SNAPSHOT"
    assert ui_payload.get("actions")[0].get("arguments").get("snapshot_scenario_id") == undo_id

    _assert_trace_invariants(events_1, expected_execution_mode="agent_mode", expect_tool_calls=False)

    events_2 = _install_trace_capture(monkeypatch)

    if streaming:
        resp2 = api.post(
            endpoint,
            json={
                "client_id": client_id,
                "messages": [
                    {
                        "role": "user",
                        "content": f'###USER_APPROVED### {{"tool_name": "RESTORE_SYSTEM_SNAPSHOT", "arguments": {{"snapshot_scenario_id": {undo_id}}}}}',
                    }
                ],
            },
        )
    else:
        resp2 = api.post(
            endpoint,
            json={
                "client_id": client_id,
                "messages": [
                    {"role": "user", "content": "undo"},
                    {"role": "assistant", "content": body1},
                    {"role": "user", "content": "מאשר"},
                ],
            },
        )

    assert resp2.status_code == 200

    with Session() as db:
        undo_after = (
            db.query(Scenario)
            .filter(Scenario.client_id == client_id)
            .filter(Scenario.scenario_name == "undo_snapshot")
            .first()
        )
        assert undo_after is None

        pending_after = _get_pending_approval_row(db=db, client_id=client_id)
        assert pending_after is None

    _assert_trace_invariants(events_2, expected_execution_mode="agent_mode", expect_tool_calls=True)


def test_stage9_guardrail_no_tool_execution_dispatch_outside_ssot() -> None:
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    app_dir = repo_root / "app"

    bad: list[str] = []
    for p in app_dir.rglob("*.py"):
        if p.name == "tool_executor.py" and "agent_execution" in str(p):
            continue

        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "from app.services.llm_chat.tool_execution import execute_tool_call" in txt:
            bad.append(str(p))
        if "tool_execution.execute_tool_call" in txt:
            bad.append(str(p))

    assert bad == []
