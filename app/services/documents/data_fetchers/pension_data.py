"""
שליפת נתוני קצבאות מה-DB
"""
from sqlalchemy.orm import Session
from typing import List
import logging

from app.models.pension_fund import PensionFund

logger = logging.getLogger(__name__)


def fetch_pension_data(db: Session, client_id: int) -> List[PensionFund]:
    """
    שולף נתוני קצבאות מה-DB
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        
    Returns:
        List[PensionFund]: רשימת קצבאות
    """
    try:
        pensions = db.query(PensionFund).filter(
            PensionFund.client_id == client_id
        ).all()
        
        logger.info(f"✅ Fetched {len(pensions)} pension funds for client {client_id}")
        return pensions
        
    except Exception as e:
        logger.error(f"❌ Error fetching pension data: {e}", exc_info=True)
        return []
