"""
System Health Router - בדיקת תקינות המערכת
מאפשר לבדוק בכל עת את תקינות הטבלאות והנתונים הקריטיים
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.database import get_db
from app.core.system_validator import SystemValidator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system_health"])


@router.get("/health")
def get_system_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    בדיקת תקינות מערכת מלאה
    
    Returns:
        {
            "status": "healthy" | "unhealthy",
            "tables": {
                "table_name": {
                    "valid": bool,
                    "error": str,
                    "description": str
                }
            },
            "summary": {
                "total_tables": int,
                "valid_tables": int,
                "invalid_tables": int
            }
        }
    """
    validator = SystemValidator(db)
    is_valid, errors = validator.validate_all()
    
    valid_count = sum(1 for r in validator.validation_results.values() if r['valid'])
    invalid_count = len(validator.validation_results) - valid_count
    
    return {
        "status": "healthy" if is_valid else "unhealthy",
        "tables": validator.validation_results,
        "summary": {
            "total_tables": len(validator.validation_results),
            "valid_tables": valid_count,
            "invalid_tables": invalid_count
        },
        "errors": errors
    }


@router.post("/health/fix")
def auto_fix_system(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    ניסיון לתקן אוטומטית נתונים חסרים
    
    Returns:
        {
            "success": bool,
            "fixed_tables": [str],
            "failed_tables": [str],
            "message": str
        }
    """
    validator = SystemValidator(db)
    
    # בדוק תקינות ראשונית
    is_valid_before, _ = validator.validate_all()
    
    if is_valid_before:
        return {
            "success": True,
            "fixed_tables": [],
            "failed_tables": [],
            "message": "המערכת תקינה - אין צורך בתיקון"
        }
    
    # נסה לתקן
    fix_results = validator.auto_fix_missing_data()
    
    # בדוק תקינות אחרי התיקון
    is_valid_after, errors_after = validator.validate_all()
    
    fixed_tables = [table for table, success in fix_results.items() if success]
    failed_tables = [table for table, success in fix_results.items() if not success]
    
    return {
        "success": is_valid_after,
        "fixed_tables": fixed_tables,
        "failed_tables": failed_tables,
        "message": (
            "התיקון הצליח - המערכת תקינה" if is_valid_after
            else f"התיקון נכשל - {len(errors_after)} שגיאות נותרו"
        ),
        "remaining_errors": errors_after if not is_valid_after else []
    }


@router.get("/health/report")
def get_validation_report(db: Session = Depends(get_db)) -> Dict[str, str]:
    """
    קבלת דוח אימות מפורט
    
    Returns:
        {
            "report": str  # דוח טקסט מפורט
        }
    """
    validator = SystemValidator(db)
    validator.validate_all()
    
    return {
        "report": validator.get_validation_report()
    }


@router.get("/health/tables/{table_name}")
def get_table_info(table_name: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    מידע מפורט על טבלה ספציפית
    
    Args:
        table_name: שם הטבלה
    
    Returns:
        {
            "table_name": str,
            "exists": bool,
            "row_count": int,
            "sample_data": List[Dict]  # 5 שורות לדוגמה
        }
    """
    from sqlalchemy import text
    
    try:
        # בדוק אם הטבלה קיימת
        result = db.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        )).fetchone()
        
        if not result:
            return {
                "table_name": table_name,
                "exists": False,
                "row_count": 0,
                "sample_data": []
            }
        
        # ספור שורות
        count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()
        row_count = count_result[0] if count_result else 0
        
        # קבל 5 שורות לדוגמה
        sample_result = db.execute(text(f"SELECT * FROM {table_name} LIMIT 5")).fetchall()
        
        # המר לרשימת מילונים
        if sample_result:
            columns = sample_result[0].keys()
            sample_data = [dict(zip(columns, row)) for row in sample_result]
        else:
            sample_data = []
        
        return {
            "table_name": table_name,
            "exists": True,
            "row_count": row_count,
            "sample_data": sample_data
        }
        
    except Exception as e:
        logger.error(f"Error getting table info for {table_name}: {e}")
        return {
            "table_name": table_name,
            "exists": False,
            "error": str(e)
        }
