"""
מודול זכאות גיל - חישוב תאריכי זכאות לפי גיל ומגדר
"""
from datetime import date


def calculate_eligibility_age(birth_date: date, gender: str, pension_start: date) -> date:
    """
    חישוב תאריך זכאות על בסיס גיל, מגדר ותאריך תחילת קצבה
    
    :param birth_date: תאריך לידה
    :param gender: מגדר ('male' או 'female')
    :param pension_start: תאריך תחילת קצבה מבוקש
    :return: תאריך זכאות (המקסימום בין גיל זכאות חוקי לתאריך תחילת קצבה)
    """
    # גיל פרישה לפי מגדר
    legal_retirement_age = date(
        birth_date.year + (67 if gender == "male" else 62), 
        birth_date.month, 
        birth_date.day
    )
    return max(legal_retirement_age, pension_start)
