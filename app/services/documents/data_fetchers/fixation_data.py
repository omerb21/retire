"""
שליפת נתוני קיבוע זכויות מה-DB
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.fixation_result import FixationResult
from app.models.grant import Grant

logger = logging.getLogger(__name__)


@dataclass
class FixationData:
    """
    מבנה נתונים לקיבוע זכויות
    """

    client: Client
    exemption_summary: Dict[str, Any]
    grants_summary: List[Dict[str, Any]]
    raw_payload: Dict[str, Any]
    raw_result: Dict[str, Any]
    eligibility_date: Optional[str]


def _grant_key_from_values(
    employer_name: Any,
    work_start_date: Any,
    work_end_date: Any,
    grant_date: Any,
) -> tuple[str, str, str, str]:
    def normalize(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    return (
        normalize(employer_name).strip(),
        normalize(work_start_date),
        normalize(work_end_date),
        normalize(grant_date),
    )


def _grant_key(grant: Dict[str, Any]) -> tuple[str, str, str, str]:
    return _grant_key_from_values(
        grant.get("employer_name"),
        grant.get("work_start_date"),
        grant.get("work_end_date"),
        grant.get("grant_date"),
    )


def _db_grant_to_summary(grant: Grant) -> Dict[str, Any]:
    grant_amount = float(getattr(grant, "grant_amount", 0.0) or 0.0)
    return {
        "employer_name": getattr(grant, "employer_name", None) or "",
        "work_start_date": (
            grant.work_start_date.isoformat() if grant.work_start_date else None
        ),
        "work_end_date": grant.work_end_date.isoformat() if grant.work_end_date else None,
        "grant_date": grant.grant_date.isoformat() if grant.grant_date else None,
        "grant_amount": grant_amount,
        "indexed_full": float(getattr(grant, "grant_indexed_amount", 0.0) or 0.0),
        "ratio_32y": float(getattr(grant, "grant_ratio", 0.0) or 0.0),
        "limited_indexed_amount": float(
            getattr(grant, "limited_indexed_amount", 0.0) or 0.0
        ),
        "impact_on_exemption": float(
            getattr(grant, "impact_on_exemption", 0.0) or 0.0
        ),
    }


def _merge_grants_with_db_rows(
    grants_summary: List[Dict[str, Any]], db_grants: List[Grant]
) -> List[Dict[str, Any]]:
    """Keep fixation grants, and append DB grant rows missing from raw_result.

    New 161ד requires all prior employers, including employers with an exempt
    grant amount of zero. Those rows may not affect the exemption calculation,
    but they still need to appear in the form and grants appendix.
    """
    merged = [grant for grant in grants_summary if isinstance(grant, dict)]
    existing_keys = {_grant_key(grant) for grant in merged}

    for db_grant in db_grants:
        candidate = _db_grant_to_summary(db_grant)
        key = _grant_key(candidate)
        if key in existing_keys:
            continue
        merged.append(candidate)
        existing_keys.add(key)

    return merged


def fetch_fixation_data(db: Session, client_id: int) -> Optional[FixationData]:
    """
    שולף נתוני קיבוע זכויות מה-DB

    Args:
        db: סשן DB
        client_id: מזהה לקוח

    Returns:
        FixationData או None אם לא נמצא
    """
    try:
        # שליפת לקוח
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(f"Client {client_id} not found")
            return None

        # שליפת תוצאות קיבוע זכויות מה-DB (האחרונות)
        fixation = (
            db.query(FixationResult)
            .filter(FixationResult.client_id == client_id)
            .order_by(desc(FixationResult.created_at))
            .first()
        )

        if not fixation or not fixation.raw_result:
            logger.warning(f"No fixation data found for client {client_id}")
            return None

        # Normalize raw_result / exemption_summary and sync with persisted fields so
        # that documents reflect the same remaining exemption and commutation totals
        # as the fixation UI and retirement flows.
        raw_result = fixation.raw_result
        if not isinstance(raw_result, dict):
            raw_result = {}

        raw_payload = fixation.raw_payload
        if not isinstance(raw_payload, dict):
            raw_payload = {}

        exemption_summary = raw_result.get("exemption_summary") or {}
        if not isinstance(exemption_summary, dict):
            exemption_summary = {}

        # remaining_exempt_capital is persisted on the fixation record and should be
        # the authoritative value for documents.
        try:
            remaining_exempt = float(
                getattr(fixation, "exempt_capital_remaining", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            remaining_exempt = 0.0
        exemption_summary["remaining_exempt_capital"] = remaining_exempt

        # total_commutations is often populated by the fixation UI when saving.
        # In retirement scenarios, the authoritative value is used_commutation
        # on the fixation record. We only override when used_commutation is
        # positive and meaningfully different from the existing value.
        try:
            used_commutation = float(getattr(fixation, "used_commutation", 0.0) or 0.0)
        except (TypeError, ValueError):
            used_commutation = 0.0

        try:
            existing_total = float(
                exemption_summary.get("total_commutations", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            existing_total = 0.0

        if used_commutation > 0 and abs(used_commutation - existing_total) > 1e-2:
            exemption_summary["total_commutations"] = used_commutation

        # Provide a final_remaining_exemption field for templates that expect it.
        exemption_summary.setdefault("final_remaining_exemption", remaining_exempt)

        raw_result["exemption_summary"] = exemption_summary
        fixation.raw_result = raw_result

        grants_summary = raw_result.get("grants", [])
        if not isinstance(grants_summary, list):
            grants_summary = []

        db_grants = db.query(Grant).filter(Grant.client_id == client_id).all()
        grants_summary = _merge_grants_with_db_rows(grants_summary, db_grants)
        raw_result["grants"] = grants_summary

        eligibility_date = raw_result.get("eligibility_date", "")

        logger.info(
            f"✅ Fetched fixation data for client {client_id}: "
            f"{len(grants_summary)} grants"
        )

        return FixationData(
            client=client,
            exemption_summary=exemption_summary,
            grants_summary=grants_summary,
            raw_payload=raw_payload,
            raw_result=raw_result,
            eligibility_date=eligibility_date,
        )

    except Exception as e:
        logger.error(f"❌ Error fetching fixation data: {e}", exc_info=True)
        return None
