"""
בדיקת תיקון חישובי המס
בודק את כל התיקונים שבוצעו:
1. ביטוח לאומי ומס בריאות אחרי גיל פרישה
2. הפרדת סוגי הכנסות עם מסים מיוחדים
3. חישוב נכון של הכנסה חייבת במס
"""

import sys
from datetime import date
from pathlib import Path

# הוספת נתיב הפרויקט
sys.path.insert(0, str(Path(__file__).parent))

from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails

def print_section(title):
    """הדפסת כותרת מודגשת"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_result(result, test_name):
    """הדפסת תוצאות בצורה מסודרת"""
    print(f"\n📊 {test_name}")
    print("-" * 80)
    print(f"סך הכנסה:           ₪{result.total_income:,.2f}")
    print(f"הכנסה חייבת במס:    ₪{result.taxable_income:,.2f}")
    print(f"הכנסה פטורה:        ₪{result.exempt_income:,.2f}")
    print(f"\nמס הכנסה:           ₪{result.income_tax:,.2f}")
    print(f"ביטוח לאומי:        ₪{result.national_insurance:,.2f}")
    print(f"מס בריאות:          ₪{result.health_tax:,.2f}")
    
    if result.special_taxes:
        print(f"\nמסים מיוחדים:")
        for tax_type, amount in result.special_taxes.items():
            print(f"  - {tax_type}: ₪{amount:,.2f}")
    
    print(f"\nסך מסים:            ₪{result.total_tax:,.2f}")
    print(f"זיכויים:            ₪{result.tax_credits_amount:,.2f}")
    print(f"מס נטו:             ₪{result.net_tax:,.2f}")
    print(f"הכנסה נטו:          ₪{result.net_income:,.2f}")
    print(f"שיעור מס אפקטיבי:   {result.effective_tax_rate:.2f}%")
    
    if result.income_breakdown:
        print(f"\nפירוט הכנסות:")
        for income in result.income_breakdown:
            if income.is_included_in_taxable:
                print(f"  ✓ {income.income_type}: ₪{income.amount:,.2f} - {income.description}")
            else:
                print(f"  ✗ {income.income_type}: ₪{income.amount:,.2f} - {income.description} (מס: ₪{income.tax_amount:,.2f})")

def test_1_young_worker_regular_income():
    """בדיקה 1: עובד צעיר (מתחת לגיל פרישה) עם הכנסה רגילה"""
    print_section("בדיקה 1: עובד צעיר - הכנסה רגילה בלבד")
    
    calculator = TaxCalculator(2024)
    
    input_data = TaxCalculationInput(
        tax_year=2024,
        personal_details=PersonalDetails(
            birth_date=date(1990, 1, 1),  # גיל 34
            marital_status="single"
        ),
        salary_income=300000,  # ₪300,000 שנתי
        pension_contributions=15000,
        study_fund_contributions=5000
    )
    
    result = calculator.calculate_comprehensive_tax(input_data)
    print_result(result, "עובד צעיר - שכר בלבד")
    
    # בדיקות
    assert result.national_insurance > 0, "❌ ביטוח לאומי צריך להיות גדול מ-0 לעובד צעיר"
    assert result.health_tax > 0, "❌ מס בריאות צריך להיות גדול מ-0 לעובד צעיר"
    assert len(result.special_taxes) == 0, "❌ לא צריכים להיות מסים מיוחדים"
    print("✅ כל הבדיקות עברו בהצלחה!")

def test_2_retiree_pension_only():
    """בדיקה 2: פנסיונר (מעל גיל פרישה) עם פנסיה בלבד"""
    print_section("בדיקה 2: פנסיונר - פנסיה בלבד")
    
    calculator = TaxCalculator(2024)
    
    input_data = TaxCalculationInput(
        tax_year=2024,
        personal_details=PersonalDetails(
            birth_date=date(1955, 1, 1),  # גיל 69
            marital_status="married"
        ),
        pension_income=150000  # ₪150,000 שנתי
    )
    
    result = calculator.calculate_comprehensive_tax(input_data)
    print_result(result, "פנסיונר - פנסיה בלבד")
    
    # בדיקות
    assert result.national_insurance == 0, f"❌ ביטוח לאומי צריך להיות 0 לפנסיונר, קיבלנו: {result.national_insurance}"
    assert result.health_tax > 0, "❌ מס בריאות צריך להיות גדול מ-0 (שיעור מופחת)"
    assert result.health_tax < 150000 * 0.05, "❌ מס בריאות לפנסיונר צריך להיות מופחת (3.1%)"
    print("✅ כל הבדיקות עברו בהצלחה!")

def test_3_mixed_income_with_rental():
    """בדיקה 3: הכנסה מעורבת - שכר + שכירות"""
    print_section("בדיקה 3: הכנסה מעורבת - שכר + שכירות")
    
    calculator = TaxCalculator(2024)
    
    input_data = TaxCalculationInput(
        tax_year=2024,
        personal_details=PersonalDetails(
            birth_date=date(1980, 1, 1),  # גיל 44
            marital_status="married"
        ),
        salary_income=200000,  # ₪200,000 שכר
        rental_income=60000,   # ₪60,000 שכירות
        pension_contributions=10000
    )
    
    result = calculator.calculate_comprehensive_tax(input_data)
    print_result(result, "שכר + שכירות")
    
    # בדיקות
    expected_rental_tax = 60000 * 0.10  # 10% מס קבוע
    assert 'rental_income' in result.special_taxes, "❌ חסר מס שכירות במסים המיוחדים"
    assert abs(result.special_taxes['rental_income'] - expected_rental_tax) < 1, \
        f"❌ מס שכירות שגוי: קיבלנו {result.special_taxes['rental_income']}, ציפינו ל-{expected_rental_tax}"
    assert result.taxable_income < result.total_income, "❌ הכנסה חייבת צריכה להיות קטנה מסך ההכנסה"
    print("✅ כל הבדיקות עברו בהצלחה!")

def test_4_capital_gains_and_dividends():
    """בדיקה 4: רווח הון ודיבידנדים"""
    print_section("בדיקה 4: רווח הון ודיבידנדים")
    
    calculator = TaxCalculator(2024)
    
    input_data = TaxCalculationInput(
        tax_year=2024,
        personal_details=PersonalDetails(
            birth_date=date(1975, 1, 1),  # גיל 49
            marital_status="single"
        ),
        salary_income=150000,
        capital_gains=80000,      # ₪80,000 רווח הון
        dividend_income=40000,    # ₪40,000 דיבידנדים
        interest_income=20000     # ₪20,000 ריבית
    )
    
    result = calculator.calculate_comprehensive_tax(input_data)
    print_result(result, "שכר + רווח הון + דיבידנדים + ריבית")
    
    # בדיקות
    expected_capital_gains_tax = 80000 * 0.25  # 25%
    expected_dividend_tax = 40000 * 0.25       # 25%
    expected_interest_tax = 20000 * 0.15       # 15%
    
    assert 'capital_gains' in result.special_taxes, "❌ חסר מס רווח הון"
    assert 'dividend_income' in result.special_taxes, "❌ חסר מס דיבידנד"
    assert 'interest_income' in result.special_taxes, "❌ חסר מס ריבית"
    
    assert abs(result.special_taxes['capital_gains'] - expected_capital_gains_tax) < 1, \
        f"❌ מס רווח הון שגוי: {result.special_taxes['capital_gains']} במקום {expected_capital_gains_tax}"
    assert abs(result.special_taxes['dividend_income'] - expected_dividend_tax) < 1, \
        f"❌ מס דיבידנד שגוי: {result.special_taxes['dividend_income']} במקום {expected_dividend_tax}"
    assert abs(result.special_taxes['interest_income'] - expected_interest_tax) < 1, \
        f"❌ מס ריבית שגוי: {result.special_taxes['interest_income']} במקום {expected_interest_tax}"
    
    print("✅ כל הבדיקות עברו בהצלחה!")

def test_5_retiree_with_all_income_types():
    """בדיקה 5: פנסיונר עם כל סוגי ההכנסות"""
    print_section("בדיקה 5: פנסיונר - כל סוגי ההכנסות")
    
    calculator = TaxCalculator(2024)
    
    input_data = TaxCalculationInput(
        tax_year=2024,
        personal_details=PersonalDetails(
            birth_date=date(1950, 1, 1),  # גיל 74
            marital_status="married",
            is_veteran=True
        ),
        pension_income=120000,
        rental_income=50000,
        capital_gains=30000,
        dividend_income=20000,
        interest_income=15000
    )
    
    result = calculator.calculate_comprehensive_tax(input_data)
    print_result(result, "פנסיונר - כל סוגי ההכנסות")
    
    # בדיקות
    assert result.national_insurance == 0, f"❌ ביטוח לאומי צריך להיות 0 לפנסיונר, קיבלנו: {result.national_insurance}"
    assert result.health_tax > 0, "❌ מס בריאות צריך להיות גדול מ-0"
    assert len(result.special_taxes) == 4, f"❌ צריכים להיות 4 מסים מיוחדים, קיבלנו: {len(result.special_taxes)}"
    assert result.exempt_income > 0, "❌ הכנסה פטורה צריכה להיות גדולה מ-0"
    print("✅ כל הבדיקות עברו בהצלחה!")

def run_all_tests():
    """הרצת כל הבדיקות"""
    print("\n" + "🔍 " * 40)
    print("מתחיל בדיקות מקיפות לתיקון חישובי המס")
    print("🔍 " * 40)
    
    try:
        test_1_young_worker_regular_income()
        test_2_retiree_pension_only()
        test_3_mixed_income_with_rental()
        test_4_capital_gains_and_dividends()
        test_5_retiree_with_all_income_types()
        
        print_section("✅ סיכום - כל הבדיקות עברו בהצלחה!")
        print("\n✓ ביטוח לאומי ומס בריאות - תקינים (כולל בדיקת גיל פרישה)")
        print("✓ הפרדת סוגי הכנסות - תקינה")
        print("✓ מסים מיוחדים - מחושבים נכון")
        print("✓ הכנסה חייבת במס - מחושבת נכון")
        print("\n" + "🎉 " * 40)
        
    except AssertionError as e:
        print(f"\n❌ בדיקה נכשלה: {e}")
        return False
    except Exception as e:
        print(f"\n❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
