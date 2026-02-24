"""
System Validator - מנגנון אימות מרכזי למערכת
מוודא שכל הטבלאות והנתונים הקריטיים קיימים ותקינים
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple, Any, Optional
import logging
import threading
import time

logger = logging.getLogger(__name__)

_validation_lock = threading.Lock()
_validation_cache: Optional[Dict[str, Any]] = None
_validation_running = False


def _build_health_payload(
    *,
    is_valid: bool,
    errors: List[str],
    tables: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    valid_count = sum(1 for r in tables.values() if r.get("valid"))
    invalid_count = len(tables) - valid_count

    return {
        "status": "healthy" if is_valid else "unhealthy",
        "tables": tables,
        "summary": {
            "total_tables": len(tables),
            "valid_tables": valid_count,
            "invalid_tables": invalid_count,
        },
        "errors": errors,
        "generated_at": time.time(),
    }


def _set_validation_cache(payload: Dict[str, Any]) -> None:
    global _validation_cache
    with _validation_lock:
        _validation_cache = payload


def get_validation_cache(
    max_age_seconds: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    with _validation_lock:
        if not _validation_cache:
            return None
        if max_age_seconds is None:
            return dict(_validation_cache)

        generated_at = _validation_cache.get("generated_at")
        if not isinstance(generated_at, (int, float)):
            return None
        if (time.time() - float(generated_at)) > max_age_seconds:
            return None

        return dict(_validation_cache)


def ensure_background_validation_running() -> bool:
    global _validation_running

    with _validation_lock:
        if _validation_running:
            return False
        _validation_running = True

    def _runner() -> None:
        global _validation_running
        try:
            run_system_validation_background()
        finally:
            with _validation_lock:
                _validation_running = False

    threading.Thread(target=_runner, daemon=True).start()
    return True


class SystemValidator:
    """מאמת תקינות המערכת בהפעלה"""

    CRITICAL_TABLES = {
        "pension_fund_coefficient": {
            "min_rows": 1000,
            "description": "מקדמי קצבה לקרנות פנסיה",
            "csv_file": "MEKEDMIM/pension_fund_coefficient.csv",
        },
        "policy_generation_coefficient": {
            "min_rows": 100,
            "description": "מקדמי קצבה לדורות ביטוח מנהלים",
            "csv_file": "MEKEDMIM/policy_generation_coefficient.csv",
        },
        "product_to_generation_map": {
            "min_rows": 5,
            "description": "מיפוי סוג מוצר לדור פוליסה",
            "csv_file": "MEKEDMIM/product_to_generation_map.csv",
        },
        "company_annuity_coefficient": {
            "min_rows": 1,
            "description": "מקדמי קצבה ספציפיים לחברות ביטוח",
            "csv_file": "MEKEDMIM/company_annuity_coefficient.csv",
        },
        # הערה: שאר הטבלאות (tax_brackets, severance_caps, pension_ceilings) מוטמעות בקוד
        # ומוגדרות ב: app/services/tax/constants/
    }

    def __init__(self, db: Session):
        self.db = db
        self.validation_results: Dict[str, Dict] = {}

    def validate_all(self) -> Tuple[bool, List[str]]:
        """
        מבצע אימות מלא של כל הטבלאות הקריטיות

        Returns:
            (is_valid, errors): האם המערכת תקינה ורשימת שגיאות
        """
        logger.info("🔍 Starting system validation...")

        errors = []
        all_valid = True

        for table_name, config in self.CRITICAL_TABLES.items():
            is_valid, error_msg = self._validate_table(table_name, config)

            self.validation_results[table_name] = {
                "valid": is_valid,
                "error": error_msg,
                "description": config["description"],
            }

            if not is_valid:
                all_valid = False
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
            else:
                logger.info(f"✅ {config['description']} - תקין")

        if all_valid:
            logger.info("✅ System validation completed successfully!")
        else:
            logger.error(f"❌ System validation failed with {len(errors)} errors")

        return all_valid, errors

    def _validate_table(self, table_name: str, config: Dict) -> Tuple[bool, str]:
        """
        מאמת טבלה בודדת

        Returns:
            (is_valid, error_message)
        """
        try:
            # אם זו טבלה שאין לה קובץ CSV, נחזיר הצלחה
            if not config.get("csv_file"):
                return True, ""

            # בדוק כמה שורות יש בטבלה
            min_rows = int(config.get("min_rows") or 0)
            count_result = self.db.execute(
                text(
                    f"SELECT COUNT(*) FROM (SELECT 1 FROM {table_name} LIMIT {min_rows}) AS t"
                )
            ).fetchone()
            row_count = count_result[0] if count_result else 0

            if row_count < config["min_rows"]:
                csv_info = f" (CSV: {config['csv_file']})" if config["csv_file"] else ""
                return False, (
                    f"טבלה '{table_name}' מכילה רק {row_count} שורות "
                    f"(מינימום נדרש: {config['min_rows']}){csv_info}"
                )

            return True, ""

        except Exception as e:
            error_text = str(e)
            if "does not exist" in error_text or "no such table" in error_text:
                return False, f"טבלה '{table_name}' לא קיימת במסד הנתונים"
            return False, f"שגיאה באימות טבלה '{table_name}': {error_text}"

    def get_validation_report(self) -> str:
        """מחזיר דוח אימות מפורט"""
        report = ["=" * 60]
        report.append("📊 דוח אימות מערכת")
        report.append("=" * 60)

        for table_name, result in self.validation_results.items():
            status = "✅" if result["valid"] else "❌"
            report.append(f"\n{status} {result['description']} ({table_name})")
            if not result["valid"]:
                report.append(f"   שגיאה: {result['error']}")

        report.append("\n" + "=" * 60)
        return "\n".join(report)

    def auto_fix_missing_data(self) -> Dict[str, bool]:
        """
        מנסה לתקן אוטומטית נתונים חסרים

        Returns:
            dict עם סטטוס תיקון לכל טבלה
        """
        logger.info("🔧 Attempting to auto-fix missing data...")

        fix_results = {}

        for table_name, config in self.CRITICAL_TABLES.items():
            if not self.validation_results.get(table_name, {}).get("valid", True):
                if config["csv_file"]:
                    try:
                        # נסה לטעון מ-CSV
                        logger.info(
                            f"📥 Loading {table_name} from {config['csv_file']}..."
                        )
                        self._load_from_csv(table_name, config["csv_file"])
                        fix_results[table_name] = True
                        logger.info(f"✅ Successfully loaded {table_name}")
                    except Exception as e:
                        fix_results[table_name] = False
                        logger.error(f"❌ Failed to load {table_name}: {e}")
                else:
                    fix_results[table_name] = False
                    logger.warning(
                        f"⚠️ {table_name} has no CSV file - manual fix required"
                    )

        return fix_results

    def _load_from_csv(self, table_name: str, csv_file: str):
        """טוען נתונים מקובץ CSV"""
        import pandas as pd
        from app.database import engine

        df = pd.read_csv(csv_file)
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info(f"✅ Loaded {len(df)} rows into {table_name}")


def validate_system_on_startup(db: Session) -> bool:
    """
    פונקציה שנקראת בהפעלת המערכת

    Returns:
        True אם המערכת תקינה, False אחרת
    """
    validator = SystemValidator(db)
    is_valid, errors = validator.validate_all()
    _set_validation_cache(
        _build_health_payload(
            is_valid=is_valid,
            errors=errors,
            tables=validator.validation_results,
        )
    )

    if not is_valid:
        logger.warning("⚠️ System validation failed - attempting auto-fix...")
        logger.warning("\n%s", validator.get_validation_report())

        # נסה לתקן אוטומטית
        validator.auto_fix_missing_data()

        # אמת שוב
        is_valid_after_fix, _errors_after_fix = validator.validate_all()
        _set_validation_cache(
            _build_health_payload(
                is_valid=is_valid_after_fix,
                errors=_errors_after_fix,
                tables=validator.validation_results,
            )
        )

        if is_valid_after_fix:
            logger.info("✅ Auto-fix successful - system is now valid")
            return True

        logger.error("❌ Auto-fix failed - manual intervention required")
        logger.error("\n%s", validator.get_validation_report())
        return False

    return True


def run_system_validation_background() -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        validate_system_on_startup(db)
    except Exception as e:
        logger.error("System validation background task failed: %s", e)
    finally:
        db.close()
