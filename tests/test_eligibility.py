"""
בדיקות יחידה למודול זכאות לקיבוע זכויות
"""
import unittest
from datetime import date, timedelta
import sys
import os

# הוספת נתיב למודול app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.services.retirement_age_service import calc_eligibility_date

# פונקציות עזר לבדיקות
def has_started_pension(pension_start_date):
    """בדיקה האם התחיל לקבל קצבה"""
    if pension_start_date is None:
        return False
    return pension_start_date <= date.today()

def is_eligible_for_fixation(birthdate, gender, pension_start_date, check_date=None):
    """בדיקה האם זכאי לקיבוע זכויות"""
    if check_date is None:
        check_date = date.today()
    
    # בדיקת גיל
    eligibility_date = calc_eligibility_date(birthdate, gender)
    age_condition_ok = check_date >= eligibility_date
    
    # בדיקת קצבה
    pension_condition_ok = has_started_pension(pension_start_date)
    
    return {
        "eligible": age_condition_ok and pension_condition_ok,
        "age_condition_ok": age_condition_ok,
        "pension_condition_ok": pension_condition_ok
    }

class TestEligibility(unittest.TestCase):
    
    def test_calc_eligibility_date_male(self):
        """בדיקת חישוב תאריך זכאות לגבר"""
        birthdate = date(1957, 1, 1)  # נולד ב-1957
        elig_date = calc_eligibility_date(birthdate, "male")
        expected = date(2024, 1, 1)  # אמור להגיע לזכאות ב-2024 (67 שנים)
        self.assertEqual(elig_date, expected)
    
    def test_calc_eligibility_date_female(self):
        """בדיקת חישוב תאריך זכאות לאישה"""
        birthdate = date(1962, 5, 15)  # נולדה ב-1962
        elig_date = calc_eligibility_date(birthdate, "female")
        expected = date(2024, 5, 15)  # אמורה להגיע לזכאות ב-2024 (62 שנים)
        self.assertEqual(elig_date, expected)
    
    def test_calc_eligibility_date_hebrew_male(self):
        """בדיקת חישוב תאריך זכאות לגבר בעברית"""
        birthdate = date(1957, 1, 1)
        elig_date = calc_eligibility_date(birthdate, "זכר")
        expected = date(2024, 1, 1)
        self.assertEqual(elig_date, expected)
    
    def test_calc_eligibility_date_hebrew_female(self):
        """בדיקת חישוב תאריך זכאות לאישה בעברית"""
        birthdate = date(1962, 5, 15)
        elig_date = calc_eligibility_date(birthdate, "נקבה")
        expected = date(2024, 5, 15)
        self.assertEqual(elig_date, expected)
    
    def test_calc_eligibility_date_unknown_gender(self):
        """בדיקת ברירת מחדל למין לא ידוע - אמור להחשב כגבר"""
        birthdate = date(1957, 1, 1)
        elig_date = calc_eligibility_date(birthdate, "unknown")
        expected = date(2024, 1, 1)  # ברירת מחדל לגבר (67 שנים)
        self.assertEqual(elig_date, expected)
    
    def test_has_started_pension_true(self):
        """בדיקה שהתחיל לקבל קצבה"""
        pension_start = date.today() - timedelta(days=30)  # התחיל לפני חודש
        self.assertTrue(has_started_pension(pension_start))
    
    def test_has_started_pension_false_future(self):
        """בדיקה שטרם התחיל לקבל קצבה - תאריך עתידי"""
        pension_start = date.today() + timedelta(days=30)  # יתחיל בעוד חודש
        self.assertFalse(has_started_pension(pension_start))
    
    def test_has_started_pension_false_none(self):
        """בדיקה שטרם התחיל לקבל קצבה - None"""
        self.assertFalse(has_started_pension(None))
    
    def test_is_eligible_male_67_with_pension(self):
        """גבר שנולד לפני 67 שנה בדיוק היום עם קצבה - זכאי"""
        today = date.today()
        birthdate = date(today.year - 67, today.month, today.day)
        pension_start = today - timedelta(days=1)  # התחיל אתמול
        
        result = is_eligible_for_fixation(birthdate, "male", pension_start, today)
        
        self.assertTrue(result["eligible"])
        self.assertTrue(result["age_condition_ok"])
        self.assertTrue(result["pension_condition_ok"])
    
    def test_is_eligible_male_66_with_pension(self):
        """גבר בן 66 עם קצבה - לא זכאי (גיל)"""
        today = date.today()
        birthdate = date(today.year - 66, today.month, today.day)
        pension_start = today - timedelta(days=1)
        
        result = is_eligible_for_fixation(birthdate, "male", pension_start, today)
        
        self.assertFalse(result["eligible"])
        self.assertFalse(result["age_condition_ok"])
        self.assertTrue(result["pension_condition_ok"])
    
    def test_is_eligible_female_62_without_pension(self):
        """אישה בת 62 ללא קצבה - לא זכאית (קצבה)"""
        today = date.today()
        birthdate = date(today.year - 62, today.month, today.day)
        pension_start = None
        
        result = is_eligible_for_fixation(birthdate, "female", pension_start, today)
        
        self.assertFalse(result["eligible"])
        self.assertTrue(result["age_condition_ok"])
        self.assertFalse(result["pension_condition_ok"])
    
    def test_is_eligible_female_62_with_pension(self):
        """אישה בת 62 עם קצבה - זכאית"""
        today = date.today()
        birthdate = date(today.year - 62, today.month, today.day)
        pension_start = today - timedelta(days=1)
        
        result = is_eligible_for_fixation(birthdate, "female", pension_start, today)
        
        self.assertTrue(result["eligible"])
        self.assertTrue(result["age_condition_ok"])
        self.assertTrue(result["pension_condition_ok"])

if __name__ == '__main__':
    unittest.main()
