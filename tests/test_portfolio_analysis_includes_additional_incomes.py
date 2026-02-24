import json
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
import app.services.llm_chat.chat_stream_orchestration_parts.stream_portfolio_analysis_generators as analysis_gens
from app.main import app
from app.models.additional_income import AdditionalIncome
from app.models.client import Client


def test_portfolio_analysis_includes_additional_incomes(monkeypatch, _test_db) -> None:
    Session = _test_db["Session"]

    with Session() as db:
        client = db.query(Client).filter(Client.id == 980000001).first()
        if client is None:
            client = Client(
                id=980000001,
                id_number_raw="980000001",
                id_number="980000001",
                full_name="Test User",
                birth_date=date(1980, 1, 1),
            )
            db.add(client)
            db.flush()
        client_id = int(getattr(client, "id", 0) or 0)

        db.add(
            AdditionalIncome(
                client_id=client_id,
                source_type="rental",
                description="Apt",
                amount=Decimal("1200"),
                frequency="monthly",
                start_date=date(2020, 1, 1),
                end_date=None,
                indexation_method="none",
                fixed_rate=None,
                tax_treatment="exempt",
                tax_rate=None,
                remarks=None,
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
            "messages": [{"role": "user", "content": "ניתוח תיק פנסיוני מלא"}],
            "pension_portfolio": [],
        },
    )

    assert resp.status_code == 200
    body = resp.text

    assert "## הכנסות נוספות (Additional Incomes)" in body
    assert "מקור: rental" in body
    assert "Apt" in body
    assert "תדירות: חודשי" in body
    assert "מס: פטור" in body
    assert 'סה"כ הכנסות נוספות נטו חודשי משוער' in body
