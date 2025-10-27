"""
שירות לחישוב מקדמי קצבה דינמיים לפי סוג מוצר, גיל ומגדר
"""
from datetime import date, datetime
from typing import Optional, Dict, Any
import logging
from sqlalchemy import text
from app.database import get_db

logger = logging.getLogger(__name__)


def get_annuity_coefficient(
    product_type: str,
    start_date: date,
    gender: str,
    retirement_age: int,
    company_name: Optional[str] = None,
    option_name: Optional[str] = None,
    survivors_option: Optional[str] = None,
    spouse_age_diff: int = 0,
    target_year: Optional[int] = None,
    birth_date: Optional[date] = None,
    pension_start_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    מחשב מקדם קצבה לפי סוג מוצר ופרמטרים
    
    Args:
        product_type: סוג המוצר (קרן פנסיה / ביטוח מנהלים)
        start_date: תאריך התחלת הפוליסה/תכנית (לזיהוי דור)
        gender: מגדר (זכר/נקבה/M/F)
        retirement_age: גיל פרישה (fallback אם אין birth_date)
        company_name: שם חברה (אופציונלי)
        option_name: שם מסלול (אופציונלי)
        survivors_option: מסלול שארים (לקרן פנסיה)
        spouse_age_diff: הפרש גיל בן זוג (לקרן פנסיה)
        target_year: שנת יעד לחישוב (אם לא מסופק - שנה נוכחית)
        birth_date: תאריך לידה (לחישוב גיל בפועל)
        pension_start_date: תאריך תחילת קצבה (תאריך מימוש)
    
    Returns:
        Dict עם:
        - factor_value: ערך המקדם
        - source_table: טבלת המקור
        - source_keys: מפתחות החיפוש
        - target_year: שנת היעד
        - guarantee_months: חודשי הבטחה (אם רלוונטי)
        - notes: הערות
    """
    
    # נרמול מגדר
    sex = normalize_gender(gender)
    
    # חישוב גיל בפועל בתאריך תחילת הקצבה
    actual_age = retirement_age  # ברירת מחדל
    if birth_date and pension_start_date:
        # חישוב גיל מדויק בתאריך תחילת הקצבה
        age_years = pension_start_date.year - birth_date.year
        # התאמה אם עדיין לא היה יום הולדת השנה
        if (pension_start_date.month, pension_start_date.day) < (birth_date.month, birth_date.day):
            age_years -= 1
        actual_age = age_years
        logger.info(
            f"[מקדם קצבה] גיל מחושב: {actual_age} "
            f"(לידה: {birth_date}, תחילת קצבה: {pension_start_date})"
        )
    
    # שנת יעד
    if target_year is None:
        target_year = datetime.now().year
    
    # בדיקה אם זו קרן פנסיה
    if is_pension_fund(product_type):
        logger.info(f"🔵 [DEBUG] Product is pension fund, calling get_pension_fund_coefficient with survivors_option='{survivors_option or 'תקנוני'}'")
        return get_pension_fund_coefficient(
            sex=sex,
            retirement_age=actual_age,
            survivors_option=survivors_option or 'תקנוני',
            spouse_age_diff=spouse_age_diff
        )
    
    # אחרת - ביטוח מנהלים
    return get_insurance_coefficient(
        start_date=start_date,
        sex=sex,
        age=actual_age,
        company_name=company_name,
        option_name=option_name,
        target_year=target_year
    )


def normalize_gender(gender: str) -> str:
    """מנרמל מגדר לפורמט אחיד"""
    if not gender:
        return 'זכר'
    
    gender_lower = gender.lower()
    if gender_lower in ['m', 'male', 'זכר', 'ז']:
        return 'זכר'
    elif gender_lower in ['f', 'female', 'נקבה', 'נ']:
        return 'נקבה'
    
    return 'זכר'  # ברירת מחדל


def is_pension_fund(product_type: str) -> bool:
    """
    בודק אם המוצר צריך להשתמש בטבלת מקדמי קרנות פנסיה
    
    קרן פנסיה, קופת גמל, קרן השתלמות → טבלת קרנות פנסיה
    כל סוג אחר (ביטוח מנהלים, פוליסות) → טבלת דורות ביטוח
    """
    if not product_type:
        return False
    
    product_lower = product_type.lower()
    
    # מוצרים שמשתמשים בטבלת קרנות פנסיה
    pension_keywords = [
        'קרן פנסיה',
        'פנסיה מקיפה', 
        'פנסיה כללית',
        'קופת גמל',
        'קרן השתלמות',
        'pension',
        'provident',
        'education'
    ]
    
    result = any(keyword in product_lower for keyword in pension_keywords)
    logger.info(f"🔵 [DEBUG] is_pension_fund('{product_type}') = {result}")
    return result


def get_pension_fund_coefficient(
    sex: str,
    retirement_age: int,
    survivors_option: str,
    spouse_age_diff: int
) -> Dict[str, Any]:
    """
    שולף מקדם קצבה לקרן פנסיה
    """
    logger.info(f"🔵 [DEBUG] get_pension_fund_coefficient called with: sex={sex}, retirement_age={retirement_age}, survivors_option={survivors_option}, spouse_age_diff={spouse_age_diff}")
    db = next(get_db())
    
    try:
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
        
        logger.info(f"🔵 [DEBUG] Query result: {result}")
        
        if result:
            factor = result[0] * result[1]  # base_coefficient * adjust_percent
            
            logger.info(
                f"[מקדם קצבה] קרן פנסיה: מין={sex}, גיל={retirement_age}, "
                f"שארים={survivors_option}, הפרש גיל={spouse_age_diff} → מקדם={factor:.2f}"
            )
            
            return {
                'factor_value': round(factor, 2),
                'source_table': 'pension_fund_coefficient',
                'source_keys': {
                    'sex': sex,
                    'retirement_age': retirement_age,
                    'survivors_option': survivors_option,
                    'spouse_age_diff': spouse_age_diff
                },
                'target_year': None,
                'guarantee_months': None,
                'notes': result[3] or '',
                'fund_name': result[2]
            }
        
        # אם לא נמצא - ברירת מחדל
        logger.warning(
            f"[מקדם קצבה] לא נמצא מקדם לקרן פנסיה, משתמש בברירת מחדל 200"
        )
        
        return {
            'factor_value': 200.0,
            'source_table': 'default',
            'source_keys': {},
            'target_year': None,
            'guarantee_months': None,
            'notes': 'ברירת מחדל - לא נמצא מקדם מתאים'
        }
        
    except Exception as e:
        logger.error(f"[מקדם קצבה] שגיאה בשליפת מקדם קרן פנסיה: {e}")
        return {
            'factor_value': 200.0,
            'source_table': 'error',
            'source_keys': {},
            'target_year': None,
            'guarantee_months': None,
            'notes': f'שגיאה: {str(e)}'
        }


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
) -> Optional[Dict[str, Any]]:
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


def get_generation_coefficient(db, generation_code: str, age: int, sex: str) -> Dict[str, Any]:
    """שולף מקדם לפי דור פוליסה, גיל ומין"""
    
    # בחירת עמודת המקדם לפי מין
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


def get_default_coefficient() -> Dict[str, Any]:
    """מחזיר מקדם ברירת מחדל"""
    return {
        'factor_value': 200.0,
        'source_table': 'default',
        'source_keys': {},
        'target_year': None,
        'guarantee_months': None,
        'notes': 'ברירת מחדל - לא נמצא מקדם מתאים'
    }
