"""
שליפת נתוני קיבוע זכויות מה-DB
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging

from app.models.client import Client
from app.models.fixation_result import FixationResult

logger = logging.getLogger(__name__)


@dataclass
class FixationData:
    """
    מבנה נתונים לקיבוע זכויות
    """
    client: Client
    exemption_summary: Dict[str, Any]
    grants_summary: List[Dict[str, Any]]
    raw_result: Dict[str, Any]
    eligibility_date: Optional[str]


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
        fixation = db.query(FixationResult).filter(
            FixationResult.client_id == client_id
        ).order_by(desc(FixationResult.created_at)).first()
        
        if not fixation or not fixation.raw_result:
            logger.warning(f"No fixation data found for client {client_id}")
            return None

        # Normalize raw_result / exemption_summary and sync with persisted fields so
        # that documents reflect the same remaining exemption and commutation totals
        # as the fixation UI and retirement flows.
        raw_result = fixation.raw_result
        if not isinstance(raw_result, dict):
            raw_result = {}

        exemption_summary = raw_result.get("exemption_summary") or {}
        if not isinstance(exemption_summary, dict):
            exemption_summary = {}

        # remaining_exempt_capital is persisted on the fixation record and should be
        # the authoritative value for documents.
        try:
            remaining_exempt = float(getattr(fixation, "exempt_capital_remaining", 0.0) or 0.0)
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
            existing_total = float(exemption_summary.get("total_commutations", 0.0) or 0.0)
        except (TypeError, ValueError):
            existing_total = 0.0

        if used_commutation > 0 and abs(used_commutation - existing_total) > 1e-2:
            exemption_summary["total_commutations"] = used_commutation

        # Provide a final_remaining_exemption field for templates that expect it.
        exemption_summary.setdefault("final_remaining_exemption", remaining_exempt)

        raw_result["exemption_summary"] = exemption_summary
        fixation.raw_result = raw_result

        grants_summary = raw_result.get('grants', [])
        eligibility_date = raw_result.get('eligibility_date', '')
        
        logger.info(
            f"✅ Fetched fixation data for client {client_id}: "
            f"{len(grants_summary)} grants"
        )
        
        return FixationData(
            client=client,
            exemption_summary=exemption_summary,
            grants_summary=grants_summary,
            raw_result=raw_result,
            eligibility_date=eligibility_date
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching fixation data: {e}", exc_info=True)
        return None
