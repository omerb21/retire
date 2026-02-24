from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.client import Client
from app.models.fixation_result import FixationResult


def get_client_fixation_response(db: Session, client_id: int) -> dict:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("client_not_found")

    fixation = (
        db.query(FixationResult)
        .filter(FixationResult.client_id == client_id)
        .order_by(desc(FixationResult.created_at))
        .first()
    )

    if not fixation or not fixation.raw_result:
        raise ValueError("no_fixation_data")

    raw_result = fixation.raw_result

    return {
        "id": fixation.id,
        "client_id": client_id,
        "created_at": fixation.created_at.isoformat() if fixation.created_at else None,
        "eligibility_year": raw_result.get("eligibility_year"),
        "exemption_summary": {
            "exemption_percentage": raw_result.get("exemption_summary", {}).get(
                "exemption_percentage", 0
            ),
            "general_exemption_percentage": raw_result.get("exemption_summary", {}).get(
                "general_exemption_percentage", 0
            ),
            "remaining_exempt_capital": raw_result.get("exemption_summary", {}).get(
                "remaining_exempt_capital", 0
            ),
            "remaining_monthly_exemption": raw_result.get("exemption_summary", {}).get(
                "remaining_monthly_exemption", 0
            ),
            "exempt_capital_initial": raw_result.get("exemption_summary", {}).get(
                "exempt_capital_initial", 0
            ),
            "eligibility_year": raw_result.get("exemption_summary", {}).get(
                "eligibility_year", 0
            ),
            "total_impact": raw_result.get("exemption_summary", {}).get(
                "total_impact", 0
            ),
        },
        "grants": raw_result.get("grants", []),
        "calculation_details": raw_result.get("calculation_details", {}),
    }
