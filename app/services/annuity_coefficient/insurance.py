"""
חישובי מקדמי קצבה לביטוח מנהלים
"""
from datetime import date
from typing import Optional, Dict, Any
import logging
from app.database import get_db
from .database import (
    get_generation_code,
    get_company_specific_coefficient,
    get_generation_coefficient
)
from .utils import get_default_coefficient

logger = logging.getLogger(__name__)


def get_insurance_coefficient(
    start_date: date,
    sex: str,
    age: int,
    company_name: Optional[str],
    option_name: Optional[str],
    target_year: int
) -> Dict[str, Any]:
    """
    שולף מקדם קצבה לביטוח מנהלים
    """
    db = next(get_db())
    
    try:
        # שלב 1: מציאת דור הפוליסה
        generation_code = get_generation_code(db, start_date)
        
        if not generation_code:
            logger.warning(f"[מקדם קצבה] לא נמצא דור לתאריך {start_date}")
            return get_default_coefficient()
        
        # שלב 2: ניסיון למצוא מקדם ספציפי לחברה
        if company_name and option_name:
            company_coef = get_company_specific_coefficient(
                db, company_name, option_name, sex, age, target_year
            )
            if company_coef:
                return company_coef
        
        # שלב 3: fallback למקדם דור (לפי גיל ומין)
        return get_generation_coefficient(db, generation_code, age, sex)
        
    except Exception as e:
        logger.error(f"[מקדם קצבה] שגיאה בשליפת מקדם ביטוח: {e}")
        return get_default_coefficient()
