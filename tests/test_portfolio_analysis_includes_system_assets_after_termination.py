import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.stream_portfolio_analysis_generators as analysis_gens
from app.main import app
from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund


def test_portfolio_analysis_includes_system_assets_after_termination(
    monkeypatch, _test_db
) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 980000002).first()
        if client is None:
            client = Client(
                id=980000002,
                id_number_raw="980000002",
                id_number="980000002",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        db.add(
            PensionFund(
                client_id=client_id,
                fund_name="קצבה ממענק פיצויים taxable - Test (Employer)",
                fund_type="monthly_pension",
                input_mode="manual",
                balance=100000.0,
                annuity_factor=200.0,
                pension_amount=1518.0,
                pension_start_date=date(2025, 1, 1),
                indexation_method="none",
                tax_treatment="taxable",
                remarks=None,
                deduction_file=None,
                conversion_source=None,
            )
        )

        db.add(
            CapitalAsset(
                client_id=client_id,
                asset_name="מענק פיצויים - משיכה הונית",
                asset_type="other",
                description="מענק פטור שנמשך",
                current_value=Decimal("35475"),
                monthly_income=Decimal("0"),
                annual_return_rate=Decimal("0"),
                payment_frequency="annually",
                start_date=date(2025, 1, 1),
                end_date=None,
                indexation_method="none",
                fixed_rate=None,
                tax_treatment="exempt",
                tax_rate=None,
                spread_years=None,
                original_principal=None,
                remarks=None,
                conversion_source=None,
            )
        )

        db.commit()

    def fake_chat_stream(*args, **kwargs):
        raise AssertionError(
            "LLM must not be called for deterministic portfolio analysis"
        )

    monkeypatch.setattr(
        stream_orch.pension_llm_service, "chat_stream", fake_chat_stream
    )

    def fake_run_retirement_scenarios(self, *args, **kwargs):
        return {"success": False}

    monkeypatch.setattr(
        analysis_gens.AgentToolsService,
        "run_retirement_scenarios",
        fake_run_retirement_scenarios,
        raising=True,
    )

    api = TestClient(app)
    resp = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client_id,
            "messages": [{"role": "user", "content": "ניתוח תיק"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text

    assert "## נכסים שנוצרו במערכת (לא מהמסלקה)" in body
    assert 'סה"כ קצבאות קיימות במערכת (ברוטו חודשי): 1,518 ₪' in body
    assert 'סה"כ נכסי הון קיימים במערכת: 35,475 ₪' in body
    assert "מענק פטור שנמשך" in body
