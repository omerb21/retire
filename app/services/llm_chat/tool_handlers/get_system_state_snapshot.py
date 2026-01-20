import json
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.capital_asset import CapitalAsset
from app.models.client import Client
from app.models.pension_fund import PensionFund
from app.models.scenario import Scenario


def handle_get_system_state_snapshot(*, args: dict, client_id: int, db: Session) -> str:
    service_version: str | None = None
    try:
        raw_version = os.environ.get("APP_VERSION") or os.environ.get("SERVICE_VERSION")
        if isinstance(raw_version, str) and raw_version.strip():
            service_version = raw_version.strip()
    except Exception:
        service_version = None

    payload = {
        "service": {
            "name": "retire",
            "version": service_version,
            "time_utc": datetime.now(timezone.utc).isoformat(),
        },
        "db": {
            "ok": True,
            "counts": {
                "clients": 0,
                "pension_funds": 0,
                "capital_assets": 0,
                "pension_portfolio_snapshots": 0,
            },
        },
    }

    try:
        payload["db"]["counts"]["clients"] = int(db.query(Client).count())
        payload["db"]["counts"]["pension_funds"] = int(db.query(PensionFund).count())
        payload["db"]["counts"]["capital_assets"] = int(db.query(CapitalAsset).count())
        payload["db"]["counts"]["pension_portfolio_snapshots"] = int(
            db.query(Scenario)
            .filter(Scenario.scenario_name == "pension_portfolio_snapshot")
            .count()
        )
    except Exception:
        payload["db"]["ok"] = False
        payload["db"]["counts"] = {
            "clients": 0,
            "pension_funds": 0,
            "capital_assets": 0,
            "pension_portfolio_snapshots": 0,
        }

    return json.dumps(payload, ensure_ascii=False)
