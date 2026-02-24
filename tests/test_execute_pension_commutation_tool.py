import json

from app.models.capital_asset import CapitalAsset
from app.models.pension_fund import PensionFund
from app.services.llm_chat.orchestration_utils_parts.blocked_balances_policy import (
    clear_current_employer_termination_plan_preview,
    store_current_employer_termination_plan_preview,
)
from app.services.llm_chat.tool_execution import execute_tool_call


def test_execute_pension_commutation_creates_asset_and_updates_fund(
    db_session, client
) -> None:
    fund = PensionFund(
        client_id=client.id,
        fund_name="קצבה לדוגמה",
        fund_type="קרן פנסיה",
        input_mode="calculated",
        balance=100000.0,
        annuity_factor=200.0,
        pension_amount=500.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        deduction_file=None,
        remarks=None,
        conversion_source=None,
    )
    db_session.add(fund)
    db_session.commit()
    db_session.refresh(fund)

    args = {
        "pension_fund_id": fund.id,
        "commutation_amount": 50000,
        "commutation_date": "2025-01-01",
        "commutation_type": "taxable",
        "confirmed": True,
    }

    result = execute_tool_call(
        "EXECUTE_PENSION_COMMUTATION",
        args,
        client.id,
        db_session,
        pension_portfolio=None,
        user_approved=True,
    )

    parsed = json.loads(result)
    assert parsed.get("success") is True
    assert parsed.get("pension_fund_id") == fund.id
    assert parsed.get("commutation_asset_id") is not None

    db_session.refresh(fund)
    assert fund.balance == 50000.0
    assert fund.pension_amount == 250.0

    asset = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.id == parsed.get("commutation_asset_id"),
        )
        .first()
    )
    assert asset is not None
    assert asset.asset_type == "deposits"
    assert (asset.remarks or "").startswith("COMMUTATION:pension_fund_id=")
    assert "amount=50000" in (asset.remarks or "")
    assert float(asset.monthly_income or 0) == 50000.0
    assert float(asset.current_value or 0) == 0.0
    assert asset.tax_treatment == "taxable"

    src = json.loads(asset.conversion_source or "{}")
    assert src.get("type") == "pension_commutation"
    assert src.get("pension_fund_id") == fund.id
    assert isinstance(src.get("original_pension"), dict)


def test_execute_process_termination_requires_approved_preview_and_overrides_args(
    db_session, client, monkeypatch
) -> None:
    import app.services.llm_chat.tool_execution as tool_execution

    clear_current_employer_termination_plan_preview(db=db_session, client_id=client.id)

    calls: dict[str, object] = {"n": 0, "args": None}

    def _fake_handle_process_termination(
        *,
        args,
        client_id,
        db,
        pension_portfolio=None,
        force_max_exemption=False,
        **_kwargs,
    ):
        calls["n"] = int(calls["n"]) + 1
        calls["args"] = dict(args or {})
        return json.dumps(
            {"success": True, "tool_name": "PROCESS_TERMINATION"}, ensure_ascii=False
        )

    monkeypatch.setattr(
        tool_execution, "handle_process_termination", _fake_handle_process_termination
    )

    res = execute_tool_call(
        "PROCESS_TERMINATION",
        {"confirmed": True, "exempt_choice": "annuity", "taxable_choice": "annuity"},
        client.id,
        db_session,
        pension_portfolio=None,
        user_approved=True,
    )
    assert isinstance(res, str)
    assert "לאשר את תכנית ברירת המחדל" in res
    assert calls["n"] == 0

    approved_template = {
        "confirmed": True,
        "exempt_choice": "redeem_with_exemption",
        "taxable_choice": "annuity",
    }
    store_current_employer_termination_plan_preview(
        db=db_session,
        client_id=client.id,
        payload={
            "plan_args": {"termination_date": "2025-01-01"},
            "termination_arguments_template": dict(approved_template),
            "awaiting_user_confirmation": False,
            "approved": True,
            "declined": False,
        },
    )

    res2 = execute_tool_call(
        "PROCESS_TERMINATION",
        {"confirmed": True, "exempt_choice": "annuity", "taxable_choice": "annuity"},
        client.id,
        db_session,
        pension_portfolio=None,
        user_approved=True,
    )
    assert calls["n"] == 1, res2
    assert isinstance(res2, str) and res2.lstrip().startswith("{"), res2
    parsed = json.loads(res2)
    assert parsed.get("success") is True
    assert calls["args"] == approved_template


def test_execute_pension_commutation_rejects_amount_over_balance(
    db_session, client
) -> None:
    fund = PensionFund(
        client_id=client.id,
        fund_name="קצבה קטנה",
        fund_type="קרן פנסיה",
        input_mode="calculated",
        balance=1000.0,
        annuity_factor=200.0,
        pension_amount=5.0,
        pension_start_date=None,
        indexation_method="none",
        tax_treatment="taxable",
    )
    db_session.add(fund)
    db_session.commit()
    db_session.refresh(fund)

    existing_for_fund = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.remarks.isnot(None),
            CapitalAsset.remarks.like(f"%pension_fund_id={fund.id}%"),
        )
        .count()
    )

    args = {
        "pension_fund_id": fund.id,
        "commutation_amount": 2000,
        "commutation_date": "2025-01-01",
        "commutation_type": "taxable",
        "confirmed": True,
    }

    result = execute_tool_call(
        "EXECUTE_PENSION_COMMUTATION",
        args,
        client.id,
        db_session,
        pension_portfolio=None,
        user_approved=True,
    )

    assert isinstance(result, str)
    assert result.lower().startswith("error:")

    db_session.refresh(fund)
    assert fund.balance == 1000.0

    after_for_fund = (
        db_session.query(CapitalAsset)
        .filter(
            CapitalAsset.client_id == client.id,
            CapitalAsset.remarks.isnot(None),
            CapitalAsset.remarks.like(f"%pension_fund_id={fund.id}%"),
        )
        .count()
    )
    assert after_for_fund == existing_for_fund
