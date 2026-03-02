import json
from datetime import date

from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario
from app.services.llm_chat.tool_handlers.execute_pension_commutation import (
    handle_execute_pension_commutation,
)


def test_commutation_from_snapshot_zeros_snapshot_and_does_not_double_balance(
    db_session, client
):
    client_id = client.id

    portfolio = [
        {
            "מספר_חשבון": "10416027",
            "שם_תכנית": "כלל תמר",
            "סוג_מוצר": "קופת גמל",
            "יתרה": 100000,
            # detailed components sum to 100000
            "תגמולי_עובד_אחרי_2000": 40000,
            "תגמולי_מעביד_אחרי_2000": 60000,
            # aggregated field that can cause double counting if summed with detailed
            "תגמולים": 100000,
            "specific_amounts": {
                "תגמולי_עובד_אחרי_2000": 40000,
                "תגמולי_מעביד_אחרי_2000": 60000,
            },
        }
    ]

    scenario = Scenario(
        client_id=client_id,
        scenario_name="pension_portfolio_snapshot",
        apply_tax_planning=False,
        apply_capitalization=False,
        apply_exemption_shield=False,
        parameters=json.dumps({"pension_portfolio": portfolio}, ensure_ascii=False),
    )
    db_session.add(scenario)
    db_session.commit()

    pf = PensionFund(
        client_id=client_id,
        fund_name="כלל תמר",
        fund_type="קופת גמל",
        input_mode="manual",
        balance=100000.0,
        annuity_factor=200.0,
        pension_amount=500.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        deduction_file="10416027",
        conversion_source=json.dumps(
            {
                "type": "pension_portfolio",
                "source": "pension_portfolio",
                "account_number": "10416027",
            },
            ensure_ascii=False,
        ),
    )
    db_session.add(pf)
    db_session.commit()
    db_session.refresh(pf)

    res = handle_execute_pension_commutation(
        args={
            "pension_fund_id": pf.id,
            "commutation_amount": 100000,
            "commutation_date": date.today().isoformat(),
            "commutation_type": "taxable",
            "confirmed": True,
        },
        client_id=client_id,
        db=db_session,
    )
    data = json.loads(res)
    assert data["success"] is True
    assert float(data["commutation_amount"]) == 100000.0

    updated = db_session.query(Scenario).filter(Scenario.id == scenario.id).first()
    params = json.loads(updated.parameters)
    updated_portfolio = params["pension_portfolio"]
    acc = updated_portfolio[0]
    assert float(acc.get("יתרה") or 0) == 0.0
    assert float(acc.get("תגמולי_עובד_אחרי_2000") or 0) == 0.0
    assert float(acc.get("תגמולי_מעביד_אחרי_2000") or 0) == 0.0
    assert float(acc.get("תגמולים") or 0) == 0.0
    assert isinstance(acc.get("specific_amounts"), dict)
    assert float(acc["specific_amounts"].get("תגמולי_עובד_אחרי_2000") or 0) == 0.0
    assert float(acc["specific_amounts"].get("תגמולי_מעביד_אחרי_2000") or 0) == 0.0
