"""
One-time maintenance: scan and fix PensionFund rows that violate the
monthly_pension invariant (active + pension_amount <= 0).

Usage:
    from app.services.pension_fund_maintenance import fix_zeroed_monthly_pensions
    result = fix_zeroed_monthly_pensions(db)
"""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.pension_fund import PensionFund

logger = logging.getLogger("app.pension_fund_maintenance")


def fix_zeroed_monthly_pensions(db: Session) -> dict[str, Any]:
    """Demote all active monthly_pension rows with pension_amount <= 0 to draft.

    Returns a summary dict with count and list of affected IDs.
    Does NOT commit — caller is responsible for committing.
    """
    rows = (
        db.query(PensionFund)
        .filter(
            PensionFund.fund_type == "monthly_pension",
            PensionFund.record_status == "active",
        )
        .filter(
            (PensionFund.pension_amount == None)  # noqa: E711
            | (PensionFund.pension_amount <= 0)
        )
        .all()
    )

    fixed_ids: list[int] = []
    for pf in rows:
        pf.record_status = "draft"
        fixed_ids.append(pf.id)
        logger.info(
            "DATA_FIX: demoted monthly_pension id=%s client_id=%s pension_amount=%s -> draft",
            pf.id,
            pf.client_id,
            pf.pension_amount,
        )

    # Best-effort agent_eyes emission
    if fixed_ids:
        try:
            from app.services.agent_eyes.event_collector import emit_event

            emit_event(
                "data_fix_applied",
                {
                    "fix": "zeroed_monthly_pension_to_draft",
                    "count": len(fixed_ids),
                    "ids": fixed_ids[:50],
                },
            )
        except Exception:
            pass

    return {
        "fixed_count": len(fixed_ids),
        "fixed_ids": fixed_ids,
    }
