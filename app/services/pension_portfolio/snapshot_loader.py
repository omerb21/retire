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
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.client_id == client_id)
        .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
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
                    product_type = (
                        item.get("סוג_מוצר")
                        or item.get("product_type")
                        or item.get("סוג מוצר")
                        or ""
                    )
                    lowered_product_type = str(product_type).lower()
                    is_education_fund = (
                        ("השתלמות" in lowered_product_type)
                        or ("education_fund" in lowered_product_type)
                        or ("klal_stud" in lowered_product_type)
                    )
                    if is_education_fund:
                        existing_edu_val = item.get("קרן_השתלמות")
                        try:
                            existing_edu_num = float(existing_edu_val or 0)
                        except (TypeError, ValueError):
                            existing_edu_num = 0.0
                        if existing_edu_num <= 0:
                            candidate_vals = [
                                item.get("יתרה"),
                                item.get("balance"),
                                item.get("תגמולים"),
                                item.get("סך_תגמולים"),
                            ]
                            edu_amount = 0.0
                            for raw in candidate_vals:
                                try:
                                    edu_amount = float(raw or 0)
                                except (TypeError, ValueError):
                                    edu_amount = 0.0
                                if edu_amount > 0:
                                    break
                            if edu_amount > 0:
                                item["קרן_השתלמות"] = edu_amount
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
