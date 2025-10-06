#!/usr/bin/env python3
"""
בדיקה שנקודות הזיכוי עובדות נכון לאחר התיקון
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails, TaxCreditInput
from datetime import date

def test_tax_credits_manual_input():
    """בדיקה שנקודות זיכוי ידניות משפיעות על חישוב המס"""
    
    print("🧪 בדיקת נקודות זיכוי ידניות...")
    
    # יצירת פרטים אישיים בסיסיים
    personal_details = PersonalDetails(
        birth_date=date(1980, 1, 1),
        marital_status="single",
        num_children=0,
        is_new_immigrant=False,
        is_veteran=False,
        is_disabled=False,
        is_student=False,
        reserve_duty_days=0
    )
    
    # בדיקה ללא נקודות זיכוי
    tax_input_no_credits = TaxCalculationInput(
        tax_year=2024,
        personal_details=personal_details,
        salary_income=200000,  # 200,000 ש"ח
        additional_tax_credits=[]
    )
    
    calculator = TaxCalculator(2024)
    result_no_credits = calculator.calculate_comprehensive_tax(tax_input_no_credits)
    
    print(f"✅ מס ללא נקודות זיכוי: ₪{result_no_credits.net_tax:,.2f}")
    
    # בדיקה עם 3 נקודות זיכוי ידניות
    manual_credits = [
        TaxCreditInput(
            code="manual_input",
            amount=3 * 2640,  # 3 נקודות × 2640 ש"ח
            description="נקודות זיכוי ידניות (3 נקודות)"
        )
    ]
    
    tax_input_with_credits = TaxCalculationInput(
        tax_year=2024,
        personal_details=personal_details,
        salary_income=200000,  # 200,000 ש"ח
        additional_tax_credits=manual_credits
    )
    
    result_with_credits = calculator.calculate_comprehensive_tax(tax_input_with_credits)
    
    print(f"✅ מס עם 3 נקודות זיכוי: ₪{result_with_credits.net_tax:,.2f}")
    print(f"✅ חיסכון במס: ₪{result_no_credits.net_tax - result_with_credits.net_tax:,.2f}")
    print(f"✅ סכום נקודות זיכוי: ₪{result_with_credits.tax_credits_amount:,.2f}")
    
    # וידוא שהחיסכון תואם לנקודות הזיכוי
    expected_savings = 3 * 2640
    actual_savings = result_no_credits.net_tax - result_with_credits.net_tax
    
    if abs(actual_savings - expected_savings) < 1:  # סובלנות של 1 ש"ח
        print("✅ נקודות הזיכוי משפיעות נכון על חישוב המס!")
        return True
    else:
        print(f"❌ שגיאה: חיסכון צפוי {expected_savings}, חיסכון בפועל {actual_savings}")
        return False

def test_calculations_service():
    """בדיקה שהשירות calculations מעביר נקודות זיכוי נכון"""
    
    print("\n🧪 בדיקת שירות החישובים...")
    
    from app.services.calculations import calculate_tax_impact_for_client
    
    # נתוני לקוח עם נקודות זיכוי
    client_data = {
        'birth_date': '1980-01-01',
        'marital_status': 'single',
        'num_children': 0,
        'is_new_immigrant': False,
        'is_veteran': False,
        'is_disabled': False,
        'is_student': False,
        'reserve_duty_days': 0,
        'tax_credit_points': 2.5,  # 2.5 נקודות זיכוי
        'annual_salary': 180000
    }
    
    try:
        result = calculate_tax_impact_for_client(client_data, 180000, 0, [])
        tax_credits = result['tax_calculation']['tax_credits']
        expected_credits = 2.5 * 2640  # 6,600 ש"ח
        
        print(f"✅ נקודות זיכוי בחישוב: ₪{tax_credits:,.2f}")
        print(f"✅ נקודות זיכוי צפויות: ₪{expected_credits:,.2f}")
        
        if abs(tax_credits - expected_credits) < 1:
            print("✅ שירות החישובים מעביר נקודות זיכוי נכון!")
            return True
        else:
            print(f"❌ שגיאה בשירות החישובים")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בשירות החישובים: {e}")
        return False

if __name__ == "__main__":
    print("🚀 בדיקת תיקון נקודות הזיכוי\n")
    
    test1_passed = test_tax_credits_manual_input()
    test2_passed = test_calculations_service()
    
    print(f"\n📊 תוצאות הבדיקה:")
    print(f"   מחשבון מס: {'✅ עבר' if test1_passed else '❌ נכשל'}")
    print(f"   שירות חישובים: {'✅ עבר' if test2_passed else '❌ נכשל'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 כל הבדיקות עברו! נקודות הזיכוי עובדות נכון.")
    else:
        print("\n⚠️ יש בעיות שצריך לתקן.")
