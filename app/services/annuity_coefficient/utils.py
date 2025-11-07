"""
פונקציות עזר לשירות מקדמי קצבה
"""
import logging

logger = logging.getLogger(__name__)


def normalize_gender(gender: str) -> str:
    """מנרמל מגדר לפורמט אחיד - מחזיר בעברית לתאימות עם הטבלה"""
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
    
    לוגיקה:
    - קרן פנסיה → טבלת קרנות פנסיה
    - קופת גמל → טבלת קרנות פנסיה
    - קרן השתלמות → טבלת קרנות פנסיה
    - כל השאר (פוליסות ביטוח, ביטוח מנהלים) → טבלת דורות ביטוח
    """
    if not product_type:
        return False
    
    product_lower = product_type.lower()
    
    # מוצרים שמשתמשים בטבלת קרנות פנסיה (רשימה ממצה)
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
    
    # לוג מפורט לדיבאג
    if result:
        logger.info(f"🔵 [DEBUG] is_pension_fund('{product_type}') = True → ישתמש בטבלת pension_fund_coefficient")
    else:
        logger.info(f"🔵 [DEBUG] is_pension_fund('{product_type}') = False → ישתמש בטבלת policy_generation_coefficient (ביטוח מנהלים)")
    
    return result


def get_default_coefficient() -> dict:
    """מחזיר מקדם ברירת מחדל"""
    return {
        'factor_value': 200.0,
        'source_table': 'default',
        'source_keys': {},
        'target_year': None,
        'guarantee_months': None,
        'notes': 'ברירת מחדל - לא נמצא מקדם מתאים'
    }
