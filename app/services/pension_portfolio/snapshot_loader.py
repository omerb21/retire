import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.scenario import Scenario
from app.schemas.llm_chat import PensionPortfolioAccount


def load_latest_pension_portfolio_snapshot(
    db: Session,
    client_id: int,
    *,
    lookback_scenarios: int = 20,
) -> tuple[list[dict[str, Any]], str] | None:
    snapshot = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
        .order_by(Scenario.created_at.desc())
        .first()
    )

    scenarios: list[Scenario] = []
    if snapshot is not None:
        scenarios.append(snapshot)

    scenarios.extend(
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .order_by(Scenario.created_at.desc())
        .limit(int(lookback_scenarios))
        .all()
    )

    for scenario in scenarios:
        if not scenario.parameters:
            continue
        try:
            params = json.loads(scenario.parameters)
        except Exception:
            continue
        portfolio = params.get("pension_portfolio")
        if isinstance(portfolio, list) and portfolio:
            snapshot_at = ""
            try:
                snapshot_at = scenario.created_at.isoformat()
            except Exception:
                snapshot_at = ""
            normalized: list[dict[str, Any]] = []
            for item in portfolio:
                if isinstance(item, dict):
                    normalized.append(item)
            if normalized:
                return normalized, snapshot_at

    return None


def load_latest_pension_portfolio_snapshot_models(
    db: Session,
    client_id: int,
    *,
    lookback_scenarios: int = 20,
) -> tuple[list[PensionPortfolioAccount], str] | None:
    raw = load_latest_pension_portfolio_snapshot(
        db,
        client_id,
        lookback_scenarios=lookback_scenarios,
    )
    if raw is None:
        return None

    portfolio, snapshot_at = raw
    models: list[PensionPortfolioAccount] = []
    for item in portfolio:
        if not isinstance(item, dict):
            continue
        try:
            models.append(PensionPortfolioAccount.model_validate(item))
        except Exception:
            continue

    if not models:
        return None
    return models, snapshot_at
