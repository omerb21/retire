import os
import json
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.current_employment import CurrentEmployer
from app.models.scenario import Scenario
from app.services.snapshot_service import SnapshotService


def test_debug_current_employer_endpoint_reports_fallback_flag(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DEBUG_ENDPOINTS_ENABLED", "1")
    monkeypatch.setenv("ADMIN_DEBUG_TOKEN", "token")

    client_id = 991000001
    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Debug CE",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    employer = CurrentEmployer(
        client_id=client_id,
        employer_name="Employer",
        start_date=date(2020, 1, 1),
        last_salary=10000.0,
        severance_accrued=None,
        other_grants={},
    )
    db_session.add(employer)
    db_session.commit()

    api = TestClient(app)
    res = api.get(
        f"/api/v1/debug/current-employer/{client_id}",
        headers={"X-Admin-Token": "token"},
        params={"retirement_age": 67},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("client_id") == client_id
    assert body.get("selected_employer", {}).get("id") == employer.id
    assert body.get("used_fallback_expected_severance") is True


def test_debug_latest_snapshot_exposes_employer_severance_field(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("DEBUG_ENDPOINTS_ENABLED", "1")
    monkeypatch.setenv("ADMIN_DEBUG_TOKEN", "token")

    client_id = 991000002
    client = db_session.query(Client).filter(Client.id == client_id).first()
    if client is None:
        client = Client(
            id=client_id,
            id_number_raw=str(client_id),
            id_number=str(client_id),
            full_name="Debug Snapshot",
            birth_date=date(1980, 1, 1),
            gender="male",
            is_active=True,
            current_employer_exists=True,
        )
        db_session.add(client)
        db_session.flush()

    snapshot_payload = {
        "snapshot": {
            "data": {
                "pension_funds": [],
                "capital_assets": [],
                "additional_incomes": [],
                "current_employer": {
                    "client_id": client_id,
                    "employer_name": "Emp",
                    "start_date": "2020-01-01",
                    "last_salary": 10000.0,
                    "severance_accrued": 252000.0,
                },
                "grants": [],
                "legacy_grants": [],
                "termination_event": None,
                "fixation_result": None,
            }
        }
    }

    row = Scenario(
        client_id=client_id,
        scenario_name="undo_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps(snapshot_payload, ensure_ascii=False),
    )
    db_session.add(row)
    db_session.commit()

    api = TestClient(app)
    res = api.get(
        f"/api/v1/debug/latest-snapshot/{client_id}",
        headers={"X-Admin-Token": "token"},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    ce = body.get("current_employer_in_snapshot") or {}
    assert ce.get("present") is True
    assert ce.get("has_severance_accrued_key") is True
    assert float(ce.get("severance_accrued") or 0.0) == 252000.0
