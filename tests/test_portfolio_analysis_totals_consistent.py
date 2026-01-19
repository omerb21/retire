import re

from fastapi.testclient import TestClient

import app.services.llm_chat.chat_stream_orchestration as stream_orch
from app.main import app


def _parse_ils_amount(text: str) -> int:
    cleaned = (text or "").replace(",", "")
    return int(cleaned)


def test_portfolio_analysis_totals_consistent(monkeypatch) -> None:
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
            "שם_תכנית": "קרן פנסיה",
            "חברה_מנהלת": "חברה",
            "סוג_מוצר": "קרן פנסיה",
            "יתרה": 10000,
        },
    ]

    response = api.post(
        "/api/v1/llm/pension-chat-stream",
        json={
            "messages": [{"role": "user", "content": "בצע ניתוח תיק פנסיוני"}],
            "pension_portfolio": portfolio,
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
