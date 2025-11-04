"""
שליפת נתוני היוונים מה-DB
"""
from sqlalchemy.orm import Session
from typing import List
import logging

from app.models.capital_asset import CapitalAsset

logger = logging.getLogger(__name__)


def fetch_commutations_data(db: Session, client_id: int) -> List[CapitalAsset]:
    """
    שולף נתוני היוונים פטורים ממס מה-DB
    
    Args:
        db: סשן DB
        client_id: מזהה לקוח
        
    Returns:
        List[CapitalAsset]: רשימת היוונים
    """
    try:
        # שליפת היוונים מנכסי הון (asset_type = 'commutation') - רק פטורים ממס
        commutations = db.query(CapitalAsset).filter(
            CapitalAsset.client_id == client_id,
            CapitalAsset.remarks.like('%pension_fund_id=%'),
            CapitalAsset.tax_treatment == 'exempt'  # רק היוונים פטורים ממס
        ).all()
        
        logger.info(f"✅ Fetched {len(commutations)} exempt commutations for client {client_id}")
        return commutations
        
    except Exception as e:
        logger.error(f"❌ Error fetching commutations data: {e}", exc_info=True)
        return []
