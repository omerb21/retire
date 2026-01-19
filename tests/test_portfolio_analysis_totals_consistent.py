import json
import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def _parse_ils_amount(text: str) -> int:
    cleaned = (
        (text or "")
        .replace(",", "")
        .replace("₪", "")
        .replace("\u00a0", " ")
        .replace(" ", "")
        .strip()
    )
    return int(cleaned)


def test_portfolio_analysis_totals_consistent(monkeypatch, db_session, client) -> None:
    def fake_chat_stream(messages, client_id=None):
        raise AssertionError("LLM must not be called for deterministic portfolio analysis")

    monkeypatch.setattr(stream_orch.pension_llm_service, "chat_stream", fake_chat_stream)

    api = TestClient(app)

    portfolio = [
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "קרן פנסיה",
            "חברה_מנהלת": "חברה",
            "סוג_מוצר": "קרן פנסיה",
            "יתרה": 10000,
            "תגמולי_עובד_אחרי_2000": 5000,
            "תגמולי_מעביד_אחרי_2000": 5000,
        },
        {
            "מספר_חשבון": "A1",
            "שם_תכנית": "קרן פנסיה (duplicate)",
            "חברה_מנהלת": "חברה",
            "סוג_מוצר": "קרן פנסיה",
            "יתרה": 10000,
            "תגמולים": 10000,
        },
        {
            "מספר_חשבון": "B1",
            "שם_תכנית": "קרן השתלמות",
            "חברה_מנהלת": "חברה",
            "סוג_מוצר": "קרן השתלמות",
            "יתרה": 7000,
        },
    ]

    from app.models.scenario import Scenario

    snapshot = Scenario(
        client_id=client.id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(snapshot)
    db_session.commit()

    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "client_id": client.id,
            "messages": [{"role": "user", "content": "בצע ניתוח תיק פנסיוני"}],
        },
    )

    assert response.status_code == 200
    body = response.text

    m_total = re.search(r"סה\"כ יתרות:\s*([\d,]+)", body)
    assert m_total is not None
    total_balance = _parse_ils_amount(m_total.group(1))

    m_pension = re.search(r"סכומים קצבתיים:\s*([\d,]+)", body)
    pension_sum = _parse_ils_amount(m_pension.group(1)) if m_pension else 0

    m_capital = re.search(r"סכומים הוניים:\s*([\d,]+)", body)
    capital_sum = _parse_ils_amount(m_capital.group(1)) if m_capital else 0

    assert total_balance >= max(pension_sum, capital_sum)
    assert abs(total_balance - (pension_sum + capital_sum)) == 0
