from datetime import date

from app.models.client import Client
from app.models.pension_fund import PensionFund


def test_system_health_includes_db_diagnostics_and_pension_fund_count(
    db_session, test_client
) -> None:
    client_obj = Client(
        id_number_raw="health-1",
        id_number="health-1",
        full_name="Health Test",
        birth_date=date(1980, 1, 1),
        gender="male",
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client_obj)
    db_session.commit()
    db_session.refresh(client_obj)

    client_id = int(client_obj.id)

    db_session.add(
        PensionFund(
            client_id=client_id,
            fund_name="קצבה A",
            fund_type="monthly_pension",
            input_mode="manual",
            balance=0.0,
            annuity_factor=200.0,
            pension_amount=123.0,
            pension_start_date=None,
            indexation_method="none",
            tax_treatment="taxable",
            deduction_file="H1",
            remarks=None,
            conversion_source=None,
        )
    )
    db_session.commit()

    resp = test_client.get("/api/v1/system/health")
    assert resp.status_code == 200
    payload = resp.json()

    assert isinstance(payload, dict)
    assert "db" in payload

    db_info = payload.get("db")
    assert isinstance(db_info, dict)
    assert db_info.get("ok") in (True, False)

    counts = db_info.get("counts")
    assert isinstance(counts, dict)
    assert int(counts.get("pension_funds") or 0) >= 1

    url = db_info.get("url")
    sqlite_path = db_info.get("sqlite_path")

    if isinstance(url, str) and url:
        assert "test_retire.db" in url
    if isinstance(sqlite_path, str) and sqlite_path:
        assert sqlite_path.lower().endswith("test_retire.db")
