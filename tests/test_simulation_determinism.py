from datetime import date

import pytest

from app.services.simulation_engine.engine import run_simulation
from app.services.simulation_engine.models import ScenarioParameters, SelectedSource, SimulationRequest


def _create_sim_client(db_session) -> int:
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
    from app.models.additional_income import AdditionalIncome
    import uuid

    unique_id = f"sim_{uuid.uuid4().hex[:10]}"
    client = Client(
        id_number_raw=unique_id,
        id_number=unique_id,
        full_name="Simulation Test Client",
        birth_date=date(1980, 1, 1),
        is_active=True,
        current_employer_exists=False,
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)

    pf = PensionFund(
        client_id=client.id,
        fund_name="Test Monthly Pension",
        fund_type="monthly_pension",
        input_mode="manual",
        balance=0.0,
        annuity_factor=1.0,
        pension_amount=1000.0,
        pension_start_date=date(2020, 1, 1),
        indexation_method="none",
        tax_treatment="taxable",
        record_status="active",
    )
    db_session.add(pf)

    inc = AdditionalIncome(
        client_id=client.id,
        source_type="salary",
        description="Test Monthly Income",
        amount=500,
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


def _fixed_request() -> SimulationRequest:
    raise RuntimeError("Use _fixed_request_for_client(client_id)")


def _fixed_request_for_client(client_id: int) -> SimulationRequest:
    return SimulationRequest(
        client_id=client_id,
        retirement_date=date(2030, 1, 15),
        selected_sources=[SelectedSource.DB],
        scenario_parameters=ScenarioParameters(),
    )


def test_simulation_determinism(db_session) -> None:
    client_id = _create_sim_client(db_session)
    req = _fixed_request_for_client(client_id)

    result1 = run_simulation(db_session, req)
    result2 = run_simulation(db_session, req)

    assert result1.model_dump() == result2.model_dump()


def test_simulation_no_writes(db_session) -> None:
    client_id = _create_sim_client(db_session)
    req = _fixed_request_for_client(client_id)

    run_simulation(db_session, req)

    assert len(db_session.new) == 0
    assert len(db_session.dirty) == 0
    assert len(db_session.deleted) == 0
