from datetime import date, datetime
from typing import Any, Dict, Optional
import logging

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.grant import Grant
from app.models.fixation_result import FixationResult
from app.services.rights_fixation import (
    calculate_full_fixation,
    get_monthly_cap,
)
from app.services.retirement.utils.pension_utils import get_effective_pension_start_date
from app.services.retirement_age_service import calc_eligibility_date

logger = logging.getLogger(__name__)


def calculate_and_save_fixation_for_client(
    db: Session, client_id: int
) -> Optional[FixationResult]:
    """Compute and persist rights fixation for a client using an existing DB session.

    This helper mirrors the logic of the /calculate and /save endpoints and is
    intended for internal server-side flows (e.g. retirement scenario execution)
    to simulate clicking "calculate" + "save" on the fixation screen.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        logger.warning(
            f"Rights fixation: client {client_id} not found, skipping auto-fixation"
        )
        return None

    grants = db.query(Grant).filter(Grant.client_id == client_id).all()

    # Determine effective pension start date from actual pensions
    pension_start_date = get_effective_pension_start_date(db, client)

    # Determine statutory eligibility date (retirement date)
    eligibility_date = (
        calc_eligibility_date(client.birth_date, client.gender)
        if client.birth_date and client.gender
        else None
    )

    # For internal flows (e.g. retirement scenarios) we always calculate and persist fixation,
    # even if the client is not yet "eligible" by today's date, so we deliberately
    # do NOT enforce the age/pension start date conditions here.
    today = date.today()

    # Build formatted data similar to the /calculate endpoint (client_id branch)
    # Effective eligibility date for calculation is the later of statutory eligibility
    # and actual pension start date, falling back to statutory eligibility or today's
    # date when needed.
    effective_eligibility_date: Optional[date] = None
    if eligibility_date:
        effective_eligibility_date = eligibility_date
        if (
            pension_start_date
            and effective_eligibility_date
            and pension_start_date > effective_eligibility_date
        ):
            effective_eligibility_date = pension_start_date

    eligibility_date_to_use = effective_eligibility_date or eligibility_date or today
    formatted_data: Dict[str, Any] = {
        "id": client_id,
        "birth_date": client.birth_date.isoformat() if client.birth_date else None,
        "gender": client.gender,
        "grants": [
            {
                "grant_amount": grant.grant_amount,
                "work_start_date": (
                    grant.work_start_date.isoformat() if grant.work_start_date else None
                ),
                "work_end_date": (
                    grant.work_end_date.isoformat() if grant.work_end_date else None
                ),
                "grant_date": (
                    grant.grant_date.isoformat()
                    if getattr(grant, "grant_date", None)
                    else None
                ),
                "employer_name": grant.employer_name,
            }
            for grant in grants
        ],
        "eligibility_date": eligibility_date_to_use.isoformat(),
        "eligibility_year": eligibility_date_to_use.year,
        "effective_pension_start_date": (
            pension_start_date.isoformat() if pension_start_date else None
        ),
    }

    logger.info("Rights fixation: calculating full fixation for client %s", client_id)
    result = calculate_full_fixation(formatted_data)

    # If calculation failed, do not save a broken result
    if not isinstance(result, dict) or result.get("error"):
        logger.error(
            "Rights fixation: calculation failed for client %s with error: %s",
            client_id,
            result.get("error"),
        )
        return None

    exemption_summary = result.get("exemption_summary", {}) or {}
    remaining_exempt_capital = (
        exemption_summary.get("remaining_exempt_capital", 0) or 0.0
    )

    # Upsert FixationResult for this client using the same semantics as /save
    existing = (
        db.query(FixationResult)
        .filter(FixationResult.client_id == client_id)
        .order_by(FixationResult.created_at.desc())
        .first()
    )

    now = datetime.now()

    if existing:
        existing.raw_result = result
        existing.raw_payload = formatted_data
        existing.exempt_capital_remaining = remaining_exempt_capital
        existing.created_at = now
        fixation_record = existing
    else:
        fixation_record = FixationResult(
            client_id=client_id,
            created_at=now,
            exempt_capital_remaining=remaining_exempt_capital,
            used_commutation=0.0,
            raw_payload=formatted_data,
            raw_result=result,
            notes="Saved automatically during retirement scenario execution",
        )
        db.add(fixation_record)

    db.flush()
    logger.info(
        "Rights fixation: auto-fixation saved for client %s (remaining_exempt_capital=%.2f)",
        client_id,
        remaining_exempt_capital,
    )
    return fixation_record


def update_fixation_exempt_pension_fields(fixation: FixationResult) -> None:
    """Update exempt pension-related fields on a FixationResult record.

    This helper is intended for server-side flows (e.g. retirement scenario execution)
    to simulate the pension-exemption part of pressing the "save" button in the
    fixation UI, based on the current exempt_capital_remaining.
    """
    try:
        raw_result = fixation.raw_result or {}
        if not isinstance(raw_result, dict):
            return

        exemption_summary = raw_result.get("exemption_summary") or {}
        if not isinstance(exemption_summary, dict):
            exemption_summary = {}

        exempt_capital_initial = float(
            exemption_summary.get("exempt_capital_initial") or 0.0
        )
        remaining_exempt_capital = float(
            getattr(fixation, "exempt_capital_remaining", 0.0) or 0.0
        )

        eligibility_year = raw_result.get("eligibility_year") or exemption_summary.get(
            "eligibility_year"
        )
        try:
            eligibility_year_int = (
                int(eligibility_year) if eligibility_year is not None else None
            )
        except (TypeError, ValueError):
            eligibility_year_int = None

        if eligibility_year_int is None:
            logger.warning(
                "Rights fixation: cannot update exempt pension fields for fixation %s - missing eligibility_year",
                getattr(fixation, "id", None),
            )
            return

        if exempt_capital_initial > 0:
            exemption_percentage = remaining_exempt_capital / exempt_capital_initial
        else:
            exemption_percentage = 0.0

        pension_ceiling = get_monthly_cap(eligibility_year_int)
        if pension_ceiling > 0:
            exempt_pension_percentage = (
                remaining_exempt_capital / 180.0
            ) / pension_ceiling
            remaining_monthly_exemption = round(
                exempt_pension_percentage * pension_ceiling, 2
            )
        else:
            exempt_pension_percentage = 0.0
            remaining_monthly_exemption = 0.0

        # Update summary fields in a way compatible with the frontend "save" logic
        exemption_summary["eligibility_year"] = eligibility_year_int
        exemption_summary["exempt_capital_initial"] = exempt_capital_initial
        exemption_summary["remaining_exempt_capital"] = remaining_exempt_capital
        exemption_summary["exemption_percentage"] = exemption_percentage
        exemption_summary["remaining_monthly_exemption"] = remaining_monthly_exemption
        exemption_summary["exempt_pension_percentage"] = exempt_pension_percentage

        # Optional diagnostic fields used by documents/reports
        used_commutation = float(getattr(fixation, "used_commutation", 0.0) or 0.0)
        exemption_summary["total_commutations"] = used_commutation
        exemption_summary["final_remaining_exemption"] = remaining_exempt_capital

        raw_result["exemption_summary"] = exemption_summary
        fixation.raw_result = raw_result

        logger.info(
            "Rights fixation: updated exempt pension fields for fixation %s (remaining_exempt_capital=%.2f, exempt_pension_percentage=%.4f)",
            getattr(fixation, "id", None),
            remaining_exempt_capital,
            exempt_pension_percentage,
        )
    except Exception as e:
        logger.error(
            "Rights fixation: failed to update exempt pension fields for fixation %s: %s",
            getattr(fixation, "id", None),
            e,
        )
