import json

from sqlalchemy.orm import Session

from app.services.retirement_scenario_execution_service import (
    execute_retirement_scenario,
)


def handle_execute_retirement_scenario(
    *, args: dict, client_id: int, db: Session
) -> str:
    scenario_id = args.get("scenario_id")
    if scenario_id is None:
        return "Error: Missing argument 'scenario_id'"

    try:
        result = execute_retirement_scenario(
            db=db,
            client_id=client_id,
            scenario_id=int(scenario_id),
        )
    except ValueError as e:
        return f"Tool Error: {str(e)}"

    return json.dumps(result, ensure_ascii=False)
