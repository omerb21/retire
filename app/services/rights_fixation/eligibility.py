"""
מודול זכאות גיל - חישוב תאריכי זכאות לפי גיל ומגדר
"""

from datetime import date


def calculate_eligibility_age(
    birth_date: date, gender: str, pension_start: date
) -> date:
    """
    חישוב תאריך זכאות על בסיס גיל, מגדר ותאריך תחילת קצבה

    :param birth_date: תאריך לידה
    :param gender: מגדר ('male' או 'female')
    :param pension_start: תאריך תחילת קצבה מבוקש
    :return: תאריך זכאות (המקסימום בין גיל זכאות חוקי לתאריך תחילת קצבה)
    """
    from app.services.retirement_age_service import get_retirement_date

    legal_retirement_date = get_retirement_date(birth_date, gender)
    return max(legal_retirement_date, pension_start)
