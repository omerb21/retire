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
        
        raw_result = fixation.raw_result
        exemption_summary = raw_result.get('exemption_summary', {})
        grants_summary = raw_result.get('grants', [])
        
        logger.info(
            f"✅ Fetched fixation data for client {client_id}: "
            f"{len(grants_summary)} grants"
        )
        
        return FixationData(
            client=client,
            exemption_summary=exemption_summary,
            grants_summary=grants_summary,
            raw_result=raw_result
        )
        
    except Exception as e:
        logger.error(f"❌ Error fetching fixation data: {e}", exc_info=True)
        return None
