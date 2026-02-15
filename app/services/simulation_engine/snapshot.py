from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models.additional_income import AdditionalIncome
from app.models.client import Client
from app.models.pension_fund import PensionFund


class ClientSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    client: dict[str, Any]
    pension_funds: list[dict[str, Any]] = Field(default_factory=list)
    additional_incomes: list[dict[str, Any]] = Field(default_factory=list)


def _coerce_number(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return float(v)


def build_client_snapshot(db: Session, client_id: int) -> dict:
    """Build a plain-data snapshot for simulation.

    Rules:
    - May read ORM to fetch rows
    - Must return only primitives (str/int/float/bool/date/None/list/dict)
    - Must not return ORM objects or lazy relationships
    - Dates must be `date` (not datetime)
    """

    client = (
        db.query(
            Client.id,
            Client.birth_date,
            Client.is_active,
            Client.current_employer_exists,
        )
        .filter(Client.id == client_id)
        .one_or_none()
    )
    if client is None:
        raise ValueError("Client not found")

    pension_rows = (
        db.query(
            PensionFund.id,
            PensionFund.fund_name,
            PensionFund.fund_type,
            PensionFund.pension_amount,
            PensionFund.pension_start_date,
            PensionFund.record_status,
            PensionFund.tax_treatment,
        )
        .filter(PensionFund.client_id == client_id)
        .all()
    )

    income_rows = (
        db.query(
            AdditionalIncome.id,
            AdditionalIncome.source_type,
            AdditionalIncome.description,
            AdditionalIncome.amount,
            AdditionalIncome.frequency,
            AdditionalIncome.start_date,
            AdditionalIncome.end_date,
            AdditionalIncome.tax_treatment,
            AdditionalIncome.tax_rate,
        )
        .filter(AdditionalIncome.client_id == client_id)
        .all()
    )

    snapshot = ClientSnapshot(
        client={
            "id": int(client.id),
            "birth_date": client.birth_date if isinstance(client.birth_date, date) else None,
            "is_active": bool(client.is_active),
            "current_employer_exists": bool(client.current_employer_exists),
        },
        pension_funds=[
            {
                "id": int(r.id),
                "fund_name": r.fund_name,
                "fund_type": r.fund_type,
                "pension_amount": r.pension_amount,
                "pension_start_date": r.pension_start_date,
                "record_status": r.record_status,
                "tax_treatment": r.tax_treatment,
            }
            for r in pension_rows
        ],
        additional_incomes=[
            {
                "id": int(r.id),
                "source_type": r.source_type,
                "description": r.description,
                "amount": _coerce_number(r.amount),
                "frequency": r.frequency,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "tax_treatment": r.tax_treatment,
                "tax_rate": _coerce_number(r.tax_rate),
            }
            for r in income_rows
        ],
    )

    return snapshot.model_dump(mode="python")
