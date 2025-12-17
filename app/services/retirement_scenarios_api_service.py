import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.scenario import Scenario


def get_client_or_raise(db: Session, client_id: int) -> Client:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("client_not_found")
    return client


def validate_retirement_age(retirement_age: int, current_age: int) -> None:
    if retirement_age < 50 or retirement_age > 80:
        raise ValueError("age_out_of_range")

    if retirement_age < current_age:
        raise ValueError("age_in_past")


def save_generated_retirement_scenarios(
    db: Session,
    *,
    client_id: int,
    retirement_age: int,
    pension_portfolio: Optional[list[dict]],
    include_current_employer_termination: bool,
    scenarios: dict,
) -> dict:
    saved_scenarios: dict = {}

    for scenario_key, scenario_data in scenarios.items():
        db.query(Scenario).filter(
            Scenario.client_id == client_id,
            Scenario.scenario_name == scenario_data["scenario_name"],
            Scenario.parameters.like(f'%"retirement_age": {retirement_age}%'),
        ).delete(synchronize_session=False)

        new_scenario = Scenario(
            client_id=client_id,
            scenario_name=scenario_data["scenario_name"],
            parameters=json.dumps(
                {
                    "retirement_age": retirement_age,
                    "scenario_type": scenario_key,
                    "pension_portfolio": pension_portfolio,
                    "include_current_employer_termination": include_current_employer_termination,
                }
            ),
            summary_results=json.dumps(scenario_data),
            cashflow_projection=None,
        )
        db.add(new_scenario)
        db.flush()

        scenario_data["scenario_id"] = new_scenario.id
        saved_scenarios[scenario_key] = scenario_data

    db.commit()
    return saved_scenarios


def load_saved_retirement_scenarios(
    db: Session,
    *,
    client_id: int,
    retirement_age: Optional[int],
) -> dict:
    query = db.query(Scenario).filter(Scenario.client_id == client_id)

    if retirement_age:
        query = query.filter(
            Scenario.parameters.like(f'%"retirement_age": {retirement_age}%')
        )

    scenarios = query.order_by(Scenario.created_at.desc()).all()

    if not scenarios:
        return {
            "success": True,
            "client_id": client_id,
            "retirement_age": retirement_age,
            "scenarios": None,
            "message": "לא נמצאו תרחישים שמורים",
        }

    organized_scenarios: dict = {}
    derived_age = retirement_age

    for scenario in scenarios:
        try:
            params = json.loads(scenario.parameters) if scenario.parameters else {}
            scenario_type = params.get("scenario_type", "unknown")
            age = params.get("retirement_age")

            if derived_age is None and age:
                derived_age = age

            if scenario.summary_results:
                summary = json.loads(scenario.summary_results)
                summary["scenario_id"] = scenario.id
                organized_scenarios[scenario_type] = summary
        except Exception:
            continue

    if organized_scenarios:
        return {
            "success": True,
            "client_id": client_id,
            "retirement_age": derived_age,
            "scenarios": organized_scenarios,
        }

    return {
        "success": True,
        "client_id": client_id,
        "retirement_age": derived_age,
        "scenarios": None,
        "message": "לא נמצאו תרחישים שמורים",
    }
