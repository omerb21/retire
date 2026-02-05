from datetime import date
import re

from app.models.pension_fund import PensionFund


def test_pension_chat_returns_monthly_pension_computed_data_and_non_empty_reply(test_client, db_session, client) -> None:
    db_session.query(PensionFund).filter(PensionFund.client_id == client.id).delete(synchronize_session=False)
    db_session.commit()

    db_session.add_all(
        [
            PensionFund(
                client_id=client.id,
                fund_name="MP-1",
                fund_type="monthly_pension",
                input_mode="manual",
                pension_amount=1000.0,
                pension_start_date=date(2020, 1, 1),
                indexation_method="none",
                tax_treatment="taxable",
            ),
            PensionFund(
                client_id=client.id,
                fund_name="MP-2",
                fund_type="monthly_pension",
                input_mode="manual",
                pension_amount=500.25,
                pension_start_date=None,
                indexation_method="none",
                tax_treatment="taxable",
            ),
        ]
    )
    db_session.commit()

    res = test_client.post(
        "/api/v1/llm/pension-chat",
        json={
            "client_id": client.id,
            "messages": [
                {
                    "role": "user",
                    "content": "תן לי סיכום monthly_pension של הקצבה הנוכחית",
                }
            ],
        },
    )

    assert res.status_code == 200
    ct = (res.headers.get("content-type") or "").lower()
    assert "application/json" in ct

    body = res.json()
    assert isinstance(body.get("reply"), str)
    assert body["reply"].strip() != ""
    assert "קצבה" in body["reply"]
    assert re.search(r"[\u0590-\u05FF]", body["reply"]) is not None

    computed = body.get("computed_data")
    assert isinstance(computed, dict)

    mp = computed.get("monthly_pension")
    assert isinstance(mp, dict)
    assert mp["current"]["count"] == 2
    assert mp["total"]["count"] == 2
