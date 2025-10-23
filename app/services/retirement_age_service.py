"""
שירות חישוב גיל פרישה לפי חוק ישראלי
מחשב את גיל הפרישה המדויק לפי תאריך לידה ומגדר
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Dict, Optional
import json
import os

# נתיב לקובץ הגדרות
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'retirement_age_settings.json')

# הגדרות ברירת מחדל לפי חוק
DEFAULT_MALE_RETIREMENT_AGE = 67

# טבלת גיל פרישה לנשים לפי תאריך לידה (בחודשים)
# המפתח הוא תאריך הלידה בפורמט YYYY-MM, הערך הוא גיל בשנים וחודשים
FEMALE_RETIREMENT_AGE_TABLE = {
    # עד מרץ 1944 - גיל 60
    ("1900-01", "1944-03"): {"years": 60, "months": 0},
    
    # אפריל עד אוגוסט 1944 - גיל 60 ו-4 חודשים
    ("1944-04", "1944-08"): {"years": 60, "months": 4},
    
    # ספטמבר 1944 עד אפריל 1945 - גיל 60 ו-8 חודשים
    ("1944-09", "1945-04"): {"years": 60, "months": 8},
    
    # מאי עד דצמבר 1945 - גיל 61
    ("1945-05", "1945-12"): {"years": 61, "months": 0},
    
    # ינואר עד אוגוסט 1946 - גיל 61 ו-4 חודשים
    ("1946-01", "1946-08"): {"years": 61, "months": 4},
    
    # ספטמבר 1946 עד אפריל 1947 - גיל 61 ו-8 חודשים
    ("1946-09", "1947-04"): {"years": 61, "months": 8},
    
    # מאי 1947 עד דצמבר 1959 - גיל 62
    ("1947-05", "1959-12"): {"years": 62, "months": 0},
    
    # ינואר עד דצמבר 1960 - גיל 62 ו-4 חודשים
    ("1960-01", "1960-12"): {"years": 62, "months": 4},
    
    # ינואר עד דצמבר 1961 - גיל 62 ו-8 חודשים
    ("1961-01", "1961-12"): {"years": 62, "months": 8},
    
    # ינואר עד דצמבר 1962 - גיל 63
    ("1962-01", "1962-12"): {"years": 63, "months": 0},
    
    # ינואר עד דצמבר 1963 - גיל 63 ו-3 חודשים
    ("1963-01", "1963-12"): {"years": 63, "months": 3},
    
    # ינואר עד דצמבר 1964 - גיל 63 ו-6 חודשים
    ("1964-01", "1964-12"): {"years": 63, "months": 6},
    
    # ינואר עד דצמבר 1965 - גיל 63 ו-9 חודשים
    ("1965-01", "1965-12"): {"years": 63, "months": 9},
    
    # ינואר עד דצמבר 1966 - גיל 64
    ("1966-01", "1966-12"): {"years": 64, "months": 0},
    
    # ינואר עד דצמבר 1967 - גיל 64 ו-3 חודשים
    ("1967-01", "1967-12"): {"years": 64, "months": 3},
    
    # ינואר עד דצמבר 1968 - גיל 64 ו-6 חודשים
    ("1968-01", "1968-12"): {"years": 64, "months": 6},
    
    # ינואר עד דצמבר 1969 - גיל 64 ו-9 חודשים
    ("1969-01", "1969-12"): {"years": 64, "months": 9},
    
    # 1970 ואילך - גיל 65
    ("1970-01", "2100-12"): {"years": 65, "months": 0},
}


def load_retirement_age_settings() -> Dict:
    """טעינת הגדרות גיל פרישה מקובץ JSON"""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading retirement age settings: {e}")
    
    # ברירת מחדל
    return {
        "male_retirement_age": DEFAULT_MALE_RETIREMENT_AGE,
        "use_legal_table_for_women": True
    }


def save_retirement_age_settings(settings: Dict) -> bool:
    """שמירת הגדרות גיל פרישה לקובץ JSON"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving retirement age settings: {e}")
        return False


def get_female_retirement_age_from_table(birth_date: date) -> Dict[str, int]:
    """
    מחזיר את גיל הפרישה לאישה לפי טבלת החוק
    
    Args:
        birth_date: תאריך לידה
        
    Returns:
        Dict עם years ו-months
    """
    birth_str = birth_date.strftime("%Y-%m")
    
    for (start, end), age_data in FEMALE_RETIREMENT_AGE_TABLE.items():
        if start <= birth_str <= end:
            return age_data
    
    # ברירת מחדל - 65 שנים (לנשים שנולדו מ-1970 ואילך)
    return {"years": 65, "months": 0}


def calculate_retirement_age(birth_date: date, gender: str) -> Dict[str, any]:
    """
    חישוב גיל פרישה מדויק לפי תאריך לידה ומגדר
    
    Args:
        birth_date: תאריך לידה
        gender: מגדר (male/female/m/f/זכר/נקבה)
        
    Returns:
        Dict עם:
        - age_years: גיל בשנים שלמות
        - age_months: חודשים נוספים
        - retirement_date: תאריך הפרישה המדויק
        - source: מקור החישוב (settings/legal_table)
    """
    settings = load_retirement_age_settings()
    
    # נרמול מגדר
    gender_normalized = (gender or "").strip().lower()
    is_male = gender_normalized in {"male", "m", "זכר"}
    
    if is_male:
        # גברים - גיל פרישה קבוע
        age_years = settings.get("male_retirement_age", DEFAULT_MALE_RETIREMENT_AGE)
        age_months = 0
        retirement_date = birth_date + relativedelta(years=age_years)
        source = "settings"
    else:
        # נשים - לפי טבלת החוק או הגדרות
        if settings.get("use_legal_table_for_women", True):
            age_data = get_female_retirement_age_from_table(birth_date)
            age_years = age_data["years"]
            age_months = age_data["months"]
            retirement_date = birth_date + relativedelta(years=age_years, months=age_months)
            source = "legal_table"
        else:
            # אם לא משתמשים בטבלה, משתמשים בהגדרה ידנית
            age_years = settings.get("female_retirement_age", 65)
            age_months = 0
            retirement_date = birth_date + relativedelta(years=age_years)
            source = "settings"
    
    return {
        "age_years": age_years,
        "age_months": age_months,
        "retirement_date": retirement_date,
        "source": source
    }


def get_retirement_age_simple(birth_date: date, gender: str) -> int:
    """
    מחזיר גיל פרישה בשנים שלמות (לתאימות לאחור)
    
    Args:
        birth_date: תאריך לידה
        gender: מגדר
        
    Returns:
        int: גיל פרישה בשנים שלמות (מעוגל כלפי מעלה)
    """
    result = calculate_retirement_age(birth_date, gender)
    age = result["age_years"]
    
    # אם יש חודשים נוספים, מעגלים כלפי מעלה
    if result["age_months"] > 0:
        age += 1
    
    return age


def get_retirement_date(birth_date: date, gender: str) -> date:
    """
    מחזיר את תאריך הפרישה המדויק
    
    Args:
        birth_date: תאריך לידה
        gender: מגדר
        
    Returns:
        date: תאריך הפרישה
    """
    result = calculate_retirement_age(birth_date, gender)
    return result["retirement_date"]


# פונקציות תאימות לאחור עם הקוד הקיים
def calc_eligibility_date(birthdate: date, gender: str) -> date:
    """חישוב תאריך זכאות לקיבוע זכויות לפי מין וגיל (תאימות לאחור)"""
    return get_retirement_date(birthdate, gender)


# קבועים לתאימות לאחור
ELIG_AGE_MALE = DEFAULT_MALE_RETIREMENT_AGE
ELIG_AGE_FEMALE = 65  # ערך ברירת מחדל לנשים
