"""
חישובי מקדמי קצבה לקרנות פנסיה
"""

import logging
from typing import Dict, Any
from app.database import get_db
from .database import get_pension_fund_coefficient_from_db

logger = logging.getLogger(__name__)


def get_pension_fund_coefficient(
    sex: str, retirement_age: int, survivors_option: str, spouse_age_diff: int
) -> Dict[str, Any]:
    """
    שולף מקדם קצבה לקרן פנסיה
    """
    logger.info(
        f"🔵 [DEBUG] get_pension_fund_coefficient called with: sex={sex}, "
        f"retirement_age={retirement_age}, survivors_option={survivors_option}, "
        f"spouse_age_diff={spouse_age_diff}"
    )
    db = next(get_db())

    try:
        result = get_pension_fund_coefficient_from_db(
            db, sex, retirement_age, survivors_option, spouse_age_diff
        )

        logger.info(f"🔵 [DEBUG] Query result: {result}")

        if result:
            factor = result["factor"]

            logger.info(
                f"[מקדם קצבה] קרן פנסיה: מין={sex}, גיל={retirement_age}, "
                f"שארים={survivors_option}, הפרש גיל={spouse_age_diff} → מקדם={factor:.2f}"
            )

            return {
                "factor_value": round(factor, 2),
                "source_table": "pension_fund_coefficient",
                "source_keys": {
                    "sex": sex,
                    "retirement_age": retirement_age,
                    "survivors_option": survivors_option,
                    "spouse_age_diff": spouse_age_diff,
                },
                "target_year": None,
                "guarantee_months": None,
                "notes": result["notes"] or "",
                "fund_name": result["fund_name"],
            }

        # אם לא נמצא - ברירת מחדל
        logger.warning(f"[מקדם קצבה] לא נמצא מקדם לקרן פנסיה, משתמש בברירת מחדל 200")

        return {
            "factor_value": 200.0,
            "source_table": "default",
            "source_keys": {},
            "target_year": None,
            "guarantee_months": None,
            "notes": "ברירת מחדל - לא נמצא מקדם מתאים",
        }

    except Exception as e:
        logger.error(f"[מקדם קצבה] שגיאה בשליפת מקדם קרן פנסיה: {e}")
        return {
            "factor_value": 200.0,
            "source_table": "error",
            "source_keys": {},
            "target_year": None,
            "guarantee_months": None,
            "notes": f"שגיאה: {str(e)}",
        }

    finally:
        try:
            db.close()
        except Exception:
            pass
