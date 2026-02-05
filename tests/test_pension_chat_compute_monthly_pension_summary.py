from datetime import date

from app.models.pension_fund import PensionFund
from app.services.pension_chat_compute import compute_monthly_pension_summary


def test_compute_monthly_pension_summary_splits_current_future_and_tax_treatment(db_session, client) -> None:
    today = date(2026, 2, 5)

    db_session.query(PensionFund).filter(PensionFund.client_id == client.id).delete(synchronize_session=False)
    db_session.commit()

    funds = [
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
            tax_treatment="exempt",
        ),
        PensionFund(
            client_id=client.id,
            fund_name="MP-3-FUTURE",
            fund_type="monthly_pension",
            input_mode="manual",
            pension_amount=10.0,
            pension_start_date=date(2030, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
        ),
        PensionFund(
            client_id=client.id,
            fund_name="NOT-MP",
            fund_type="other",
            input_mode="manual",
            pension_amount=9999.0,
            pension_start_date=date(2020, 1, 1),
            indexation_method="none",
            tax_treatment="taxable",
        ),
    ]

    db_session.add_all(funds)
    db_session.commit()

    payload = compute_monthly_pension_summary(db_session, client.id, today)

    assert payload.get("client_id") == client.id
    assert payload.get("today") == today.isoformat()

    mp = payload.get("monthly_pension")
    assert isinstance(mp, dict)

    current = mp.get("current")
    future = mp.get("future")
    total = mp.get("total")

    assert current["count"] == 2
    assert future["count"] == 1
    assert total["count"] == 3

    assert current["taxable"]["count"] == 1
    assert current["exempt"]["count"] == 1

    assert current["sum"] == 1500.25
    assert current["taxable"]["sum"] == 1000.0
    assert current["exempt"]["sum"] == 500.25
    assert future["sum"] == 10.0
    assert total["sum"] == 1510.25

    assert isinstance(current.get("items"), list)
    assert isinstance(future.get("items"), list)

    for it in current["items"] + future["items"]:
        assert "id" in it
        assert "amount" in it
        assert "start_date" in it
        assert "tax_treatment" in it
