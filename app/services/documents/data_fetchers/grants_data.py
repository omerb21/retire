"""
שליפת נתוני מענקים מה-DB
"""
from sqlalchemy.orm import Session
from typing import List, Dict
import logging

from app.models.grant import Grant

logger = logging.getLogger(__name__)


def fetch_grants_data(db: Session, client_id: int) -> Dict[str, Dict[str, str]]:
    """
    שולף נתוני מענקים מה-DB ומחזיר מיפוי לפי שם מעסיק
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        
    Returns:
        Dict: מיפוי של שם מעסיק לתאריכי עבודה
    """
    try:
        grants = db.query(Grant).filter(Grant.client_id == client_id).all()
        
        grants_dates_map = {
            g.employer_name: {
                'work_start_date': g.work_start_date.strftime("%d/%m/%Y") if g.work_start_date else "-",
                'work_end_date': g.work_end_date.strftime("%d/%m/%Y") if g.work_end_date else "-"
            }
            for g in grants
        }
        
        logger.info(f"✅ Fetched {len(grants)} grants for client {client_id}")
        return grants_dates_map
        
    except Exception as e:
        logger.error(f"❌ Error fetching grants data: {e}", exc_info=True)
        return {}
