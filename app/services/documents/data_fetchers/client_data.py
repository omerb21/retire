"""
שליפת נתוני לקוח מה-DB
"""
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.models.client import Client

logger = logging.getLogger(__name__)


def fetch_client_data(db: Session, client_id: int) -> Optional[Client]:
    """
    שולף נתוני לקוח מה-DB
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        
    Returns:
        Client או None אם לא נמצא
    """
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        
        if not client:
            logger.warning(f"Client {client_id} not found")
            return None
        
        logger.info(f"✅ Client data loaded: {client.first_name} {client.last_name}")
        return client
        
    except Exception as e:
        logger.error(f"❌ Error fetching client data: {e}", exc_info=True)
        return None
