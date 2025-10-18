"""
System Snapshot API Endpoints
נקודות קצה לשמירה ושחזור מצב מערכת
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Dict
import logging

from app.database import get_db
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/v1/clients", tags=["snapshots"])
logger = logging.getLogger(__name__)


@router.post("/{client_id}/snapshot/save")
def save_system_snapshot(
    client_id: int = Path(..., description="Client ID"),
    snapshot_name: str = Body(None, embed=True, description="שם אופציונלי ל-snapshot"),
    db: Session = Depends(get_db)
):
    """
    💾 שמירת snapshot מלא של מצב הלקוח
    
    שומר:
    - קצבאות (Pension Funds)
    - נכסי הון (Capital Assets)
    - הכנסות נוספות (Additional Income)
    - מעסיק נוכחי (Current Employer)
    - מענקים (Grants)
    - עזיבת עבודה (Termination Event)
    - קיבוע זכויות (Fixation Result)
    """
    logger.info(f"💾 Snapshot save request for client {client_id}")
    
    try:
        service = SnapshotService(db)
        result = service.save_snapshot(client_id, snapshot_name)
        
        logger.info(f"✅ Snapshot saved: {result['total_items']} items")
        
        return result
        
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to save snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה בשמירת snapshot: {str(e)}")


@router.post("/{client_id}/snapshot/restore")
def restore_system_snapshot(
    snapshot_data: Dict = Body(..., description="נתוני snapshot לשחזור"),
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """
    ♻️ שחזור מצב מערכת מ-snapshot
    
    מחזיר את כל הנתונים למצב ששמור ב-snapshot:
    - מוחק את כל הנתונים הקיימים
    - משחזר את כל הנתונים מה-snapshot
    
    ⚠️ אזהרה: פעולה זו בלתי הפיכה!
    """
    logger.info(f"♻️ Snapshot restore request for client {client_id}")
    
    try:
        service = SnapshotService(db)
        result = service.restore_snapshot(client_id, snapshot_data)
        
        logger.info(f"✅ Snapshot restored: deleted {result['deleted_count']}, restored {result['restored_count']}")
        
        return result
        
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to restore snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"שגיאה בשחזור snapshot: {str(e)}")


@router.get("/{client_id}/snapshot/info")
def get_snapshot_info(
    client_id: int = Path(..., description="Client ID"),
    db: Session = Depends(get_db)
):
    """
    📊 קבלת מידע על המצב הנוכחי של הלקוח
    
    מחזיר סטטיסטיקה על כמות הפריטים במערכת
    """
    logger.info(f"📊 Snapshot info request for client {client_id}")
    
    try:
        service = SnapshotService(db)
        
        # קריאת snapshot זמני כדי לקבל סטטיסטיקה
        snapshot = service.save_snapshot(client_id, "temp")
        
        return {
            "client_id": client_id,
            "total_items": snapshot["total_items"],
            "breakdown": {
                "pension_funds": len(snapshot["snapshot"]["data"]["pension_funds"]),
                "capital_assets": len(snapshot["snapshot"]["data"]["capital_assets"]),
                "additional_incomes": len(snapshot["snapshot"]["data"]["additional_incomes"]),
                "grants": len(snapshot["snapshot"]["data"]["grants"]),
                "has_employer": snapshot["snapshot"]["data"]["current_employer"] is not None,
                "has_termination": snapshot["snapshot"]["data"]["termination_event"] is not None,
                "has_fixation": snapshot["snapshot"]["data"]["fixation_result"] is not None
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Failed to get snapshot info: {e}")
        raise HTTPException(status_code=500, detail=f"שגיאה בקבלת מידע: {str(e)}")
