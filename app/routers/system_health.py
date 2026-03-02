"""
System Health Router - בדיקת תקינות המערכת
מאפשר לבדוק בכל עת את תקינות הטבלאות והנתונים הקריטיים
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.system_validator import (
    SystemValidator,
    ensure_background_validation_running,
    get_validation_cache,
)
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["system_health"])


def _get_db_diagnostics(db: Session) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": True,
        "url": None,
        "sqlite_path": None,
        "counts": {"pension_funds": 0},
    }

    bind = None
    try:
        bind = db.get_bind()
    except Exception:
        bind = None

    if bind is None:
        payload["ok"] = False
        return payload

    try:
        engine_url = make_url(str(bind.url))
        if engine_url.password is not None:
            safe_url = str(engine_url.set(password="***"))
        else:
            safe_url = str(engine_url)
        payload["url"] = safe_url

        if (
            (engine_url.drivername or "").startswith("sqlite")
            and engine_url.database
            and engine_url.database != ":memory:"
        ):
            payload["sqlite_path"] = engine_url.database
    except Exception:
        payload["ok"] = False

    try:
        inspector = inspect(bind)
        if inspector.has_table("pension_funds"):
            row = db.execute(text("SELECT COUNT(*) FROM pension_funds")).fetchone()
            payload["counts"]["pension_funds"] = int(row[0] if row else 0)
    except Exception:
        payload["ok"] = False

    return payload


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
    cached = get_validation_cache(max_age_seconds=5 * 60)
    if cached is not None:
        ensure_background_validation_running()
        cached.pop("generated_at", None)
        cached["db"] = _get_db_diagnostics(db)
        return cached

    ensure_background_validation_running()
    payload = {
        "status": "unhealthy",
        "tables": {},
        "summary": {
            "total_tables": 0,
            "valid_tables": 0,
            "invalid_tables": 0,
        },
        "errors": ["System validation is still running"],
    }

    payload["db"] = _get_db_diagnostics(db)
    return payload


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
            "message": "המערכת תקינה - אין צורך בתיקון",
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
            "התיקון הצליח - המערכת תקינה"
            if is_valid_after
            else f"התיקון נכשל - {len(errors_after)} שגיאות נותרו"
        ),
        "remaining_errors": errors_after if not is_valid_after else [],
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
    cached = get_validation_cache(max_age_seconds=5 * 60)
    if cached is not None:
        tables = cached.get("tables") or {}
        lines = ["=" * 60, "📊 דוח אימות מערכת", "=" * 60]
        for table_name, result in tables.items():
            status = "✅" if result.get("valid") else "❌"
            description = result.get("description") or ""
            lines.append(f"\n{status} {description} ({table_name})")
            if not result.get("valid") and result.get("error"):
                lines.append(f"   שגיאה: {result.get('error')}")
        lines.append("\n" + "=" * 60)
        return {"report": "\n".join(lines)}

    ensure_background_validation_running()
    return {"report": "System validation is still running"}


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
    try:
        engine = db.get_bind()
        inspector = inspect(engine)

        if not inspector.has_table(table_name):
            return {
                "table_name": table_name,
                "exists": False,
                "row_count": 0,
                "sample_data": [],
            }

        # ספור שורות
        count_result = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).fetchone()
        row_count = count_result[0] if count_result else 0

        # קבל 5 שורות לדוגמה
        sample_result = db.execute(
            text(f"SELECT * FROM {table_name} LIMIT 5")
        ).fetchall()

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
            "sample_data": sample_data,
        }

    except Exception as e:
        logger.error(f"Error getting table info for {table_name}: {e}")
        return {"table_name": table_name, "exists": False, "error": str(e)}
