from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.scenario import Scenario


def get_client_or_raise(db: Session, client_id: int) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("client_not_found")
    return client


def get_scenarios_for_client_or_raise(
    db: Session,
    client_id: int,
    scenario_ids: List[int],
) -> List[Scenario]:
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.id.in_(scenario_ids), Scenario.client_id == client_id)
        .all()
    )
    if len(scenarios) != len(scenario_ids):
        raise ValueError("scenario_mismatch")
    return scenarios


def parse_scenario_ids_csv(scenario_ids: str) -> List[int]:
    try:
        return [int(item.strip()) for item in scenario_ids.split(",")]
    except Exception as exc:
        raise ValueError("invalid_scenario_ids") from exc


def get_or_create_default_scenario(
    db: Session, client_id: int, scenario_id: int
) -> Scenario:
    scenario = (
        db.query(Scenario)
        .filter(Scenario.id == scenario_id, Scenario.client_id == client_id)
        .first()
    )
    if scenario:
        return scenario

    scenario = Scenario(
        client_id=client_id,
        scenario_name="דוח ברירת מחדל",
        parameters="{}",
        summary_results="{}",
        cashflow_projection="{}",
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario
