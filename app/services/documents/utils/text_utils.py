"""
פונקציות עזר לטיפול בטקסט
"""
import re


def sanitize_filename(filename: str) -> str:
    """
    מנקה שם קובץ מתווים לא חוקיים
    
    Args:
        filename: שם קובץ לניקוי
        
    Returns:
        str: שם קובץ נקי
    """
    # הסרת תווים לא חוקיים
    clean = re.sub(r'[^\w\s-]', '', filename).strip()
    # החלפת רווחים מרובים ברווח יחיד
    clean = re.sub(r'\s+', ' ', clean)
    return clean
