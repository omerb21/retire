"""
פעולות מסד נתונים לשירות מקדמי קצבה
"""
from datetime import date
from typing import Optional
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def get_generation_code(db, start_date: date) -> Optional[str]:
    """מוצא את קוד הדור לפי תאריך התחלה"""
    query = text("""
        SELECT generation_code
        FROM product_to_generation_map
        WHERE product_type = 'ביטוח מנהלים'
          AND :start_date BETWEEN rule_from_date AND rule_to_date
        LIMIT 1
    """)
    
    result = db.execute(query, {'start_date': start_date.isoformat()}).fetchone()
    return result[0] if result else None


def get_company_specific_coefficient(
    db, company_name: str, option_name: str, sex: str, age: int, target_year: int
) -> Optional[dict]:
    """מחפש מקדם ספציפי לחברה"""
    query = text("""
        SELECT 
            base_coefficient,
            annual_increment_rate,
            base_year,
            notes
        FROM company_annuity_coefficient
        WHERE company_name = :company_name
          AND option_name = :option_name
          AND sex = :sex
          AND age = :age
        LIMIT 1
    """)
    
    result = db.execute(query, {
        'company_name': company_name,
        'option_name': option_name,
        'sex': sex,
        'age': age
    }).fetchone()
    
    if result:
        base_coef = result[0]
        annual_rate = result[1]
        base_year = result[2]
        notes = result[3]
        
        # חישוב מקדם מותאם לשנת יעד
        factor = base_coef * (1 + annual_rate * (target_year - base_year))
        
        logger.info(
            f"[מקדם קצבה] חברה={company_name}, מסלול={option_name}, "
            f"מין={sex}, גיל={age}, שנה={target_year} → מקדם={factor:.2f}"
        )
        
        return {
            'factor_value': round(factor, 2),
            'source_table': 'company_annuity_coefficient',
            'source_keys': {
                'company_name': company_name,
                'option_name': option_name,
                'sex': sex,
                'age': age
            },
            'target_year': target_year,
            'guarantee_months': None,
            'notes': notes or ''
        }
    
    return None


def get_generation_coefficient(db, generation_code: str, age: int, sex: str) -> dict:
    """שולף מקדם לפי דור פוליסה, גיל ומין"""
    from .utils import get_default_coefficient
    
    # בחירת עמודת המקדם לפי מין (sex כבר מנורמל ל-זכר/נקבה)
    coef_column = 'male_coefficient' if sex == 'זכר' else 'female_coefficient'
    
    query = text(f"""
        SELECT 
            {coef_column},
            guarantee_months,
            generation_label,
            notes
        FROM policy_generation_coefficient
        WHERE generation_code = :generation_code
          AND age = :age
        LIMIT 1
    """)
    
    result = db.execute(query, {
        'generation_code': generation_code,
        'age': age
    }).fetchone()
    
    if result:
        factor = result[0]
        guarantee = result[1]
        label = result[2]
        notes = result[3]
        
        # בדיקה אם המקדם קיים (לא NULL)
        if factor is None or factor == 0:
            logger.warning(
                f"[מקדם קצבה] לא נמצא מקדם ל-{sex} בגיל {age}, דור {generation_code}"
            )
            return get_default_coefficient()
        
        logger.info(
            f"[מקדם קצבה] דור={generation_code} ({label}), גיל={age}, מין={sex} → מקדם={factor:.2f}"
        )
        
        return {
            'factor_value': round(factor, 2),
            'source_table': 'policy_generation_coefficient',
            'source_keys': {
                'generation_code': generation_code,
                'age': age,
                'sex': sex
            },
            'target_year': None,
            'guarantee_months': guarantee,
            'notes': notes or ''
        }
    
    logger.warning(
        f"[מקדם קצבה] לא נמצאה שורה עבור דור={generation_code}, גיל={age}"
    )
    return get_default_coefficient()


def get_pension_fund_coefficient_from_db(
    db, sex: str, retirement_age: int, survivors_option: str, spouse_age_diff: int
) -> Optional[dict]:
    """שולף מקדם קצבה לקרן פנסיה מהמסד נתונים"""
    query = text("""
        SELECT 
            base_coefficient,
            adjust_percent,
            fund_name,
            notes
        FROM pension_fund_coefficient
        WHERE sex = :sex
          AND retirement_age = :retirement_age
          AND survivors_option = :survivors_option
          AND spouse_age_diff = :spouse_age_diff
        ORDER BY id DESC
        LIMIT 1
    """)
    
    result = db.execute(query, {
        'sex': sex,
        'retirement_age': retirement_age,
        'survivors_option': survivors_option,
        'spouse_age_diff': spouse_age_diff
    }).fetchone()
    
    if result:
        base_coef = result[0]
        adjust_pct = result[1]
        fund_name = result[2]
        notes = result[3]
        
        # אם adjust_percent הוא 0, משתמשים רק ב-base_coefficient
        # אחרת, מכפילים (adjust_percent צריך להיות 1.0 לברירת מחדל)
        if adjust_pct == 0:
            factor = base_coef
        else:
            factor = base_coef * adjust_pct
        
        return {
            'factor': factor,
            'fund_name': fund_name,
            'notes': notes
        }
    
    return None
