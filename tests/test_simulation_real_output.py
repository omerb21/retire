from datetime import date

from app.services.simulation_engine.engine import run_simulation
from app.services.simulation_engine.models import (
    ScenarioParameters,
    SelectedSource,
    SimulationRequest,
)


def _create_sim_client_with_data(db_session) -> int:
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
    from app.models.additional_income import AdditionalIncome
    import uuid

    unique_id = f"sim_real_{uuid.uuid4().hex[:10]}"
    client = Client(
        id_number_raw=unique_id,
        id_number=unique_id,
        full_name="Simulation Real Output Client",
        birth_date=date(1980, 1, 1),
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)

    pf = PensionFund(
        client_id=client.id,
        fund_name="Real Monthly Pension",
        fund_type="monthly_pension",
        input_mode="manual",
        balance=0.0,
        annuity_factor=1.0,
        pension_amount=1200.0,
        pension_start_date=date(2020, 1, 1),
        indexation_method="none",
        tax_treatment="taxable",
        record_status="active",
    )
    db_session.add(pf)

    inc = AdditionalIncome(
        client_id=client.id,
        source_type="salary",
        description="Real Monthly Income",
        amount=800,
        frequency="monthly",
        start_date=date(2020, 1, 1),
        end_date=None,
        indexation_method="none",
        tax_treatment="taxable",
        tax_rate=None,
    )
    db_session.add(inc)
    db_session.commit()

    return client.id


def test_simulation_real_output_not_all_zeros(db_session) -> None:
    client_id = _create_sim_client_with_data(db_session)

    req = SimulationRequest(
        client_id=client_id,
        retirement_date=date(2030, 1, 15),
        selected_sources=[SelectedSource.DB],
        scenario_parameters=ScenarioParameters(),
    )

    result = run_simulation(db_session, req)
    assert len(result.monthly_cashflow) >= 1

    assert any(
        (item.gross != 0.0 or item.net != 0.0) for item in result.monthly_cashflow
    )
