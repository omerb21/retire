"""
בדיקת 3 התיקונים הקריטיים בחישוב המס
"""
from datetime import date
from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails

def test_pension_timing_fix():
    """בדיקה 1: תזמון קצבאות - 1 חודש לעומת 12 חודשים"""
    print("\n" + "="*80)
    print("בדיקה 1: תזמון קצבאות")
    print("="*80)
    
    personal_details = PersonalDetails(
        birth_date=date(1958, 1, 1),
        marital_status="married",
        num_children=0
    )
    
    calculator = TaxCalculator(tax_year=2025)
    
    # תרחיש א': קצבה חודשית של 10,000 ש"ח, רק חודש אחד (דצמבר 2025)
    input_1_month = TaxCalculationInput(
        tax_year=2025,
        personal_details=personal_details,
        pension_income=10000 * 12,  # הסכום השנתי המלא
        pension_months_in_year=1,   # רק חודש אחד
        business_income=50000
    )
    
    result_1_month = calculator.calculate_comprehensive_tax(input_1_month)
    
    # תרחיש ב': אותה קצבה חודשית, 12 חודשים (2026)
    input_12_months = TaxCalculationInput(
        tax_year=2026,
        personal_details=personal_details,
        pension_income=10000 * 12,  # הסכום השנתי המלא
        pension_months_in_year=12,  # 12 חודשים
        business_income=50000
    )
    
    result_12_months = calculator.calculate_comprehensive_tax(input_12_months)
    
    print(f"\nתרחיש א' - חודש אחד (דצמבר 2025):")
    print(f"  הכנסה מקצבה (שנתי): {input_1_month.pension_income:,.2f}")
    print(f"  מספר חודשים: {input_1_month.pension_months_in_year}")
    print(f"  הכנסה חייבת: {result_1_month.taxable_income:,.2f}")
    print(f"  מס נטו: {result_1_month.net_tax:,.2f}")
    
    print(f"\nתרחיש ב' - 12 חודשים (2026):")
    print(f"  הכנסה מקצבה (שנתי): {input_12_months.pension_income:,.2f}")
    print(f"  מספר חודשים: {input_12_months.pension_months_in_year}")
    print(f"  הכנסה חייבת: {result_12_months.taxable_income:,.2f}")
    print(f"  מס נטו: {result_12_months.net_tax:,.2f}")
    
    print(f"\nהפרש במס: {result_12_months.net_tax - result_1_month.net_tax:,.2f}")
    
    if result_1_month.net_tax == result_12_months.net_tax:
        print("❌ שגיאה: המס זהה למרות הבדל במספר החודשים!")
        return False
    else:
        print("✅ תוקן: המס שונה בהתאם למספר החודשים")
        return True


def test_business_income_tax_change():
    """בדיקה 2: שינוי במס על הכנסה מעסק כאשר מוסיפים קצבה"""
    print("\n" + "="*80)
    print("בדיקה 2: שינוי במס על הכנסה מעסק")
    print("="*80)
    
    personal_details = PersonalDetails(
        birth_date=date(1958, 1, 1),
        marital_status="married",
        num_children=0
    )
    
    calculator = TaxCalculator(tax_year=2025)
    
    # תרחיש א': רק הכנסה מעסק
    input_business_only = TaxCalculationInput(
        tax_year=2025,
        personal_details=personal_details,
        business_income=50000
    )
    
    result_business_only = calculator.calculate_comprehensive_tax(input_business_only)
    
    # תרחיש ב': הכנסה מעסק + קצבה גבוהה
    input_with_pension = TaxCalculationInput(
        tax_year=2025,
        personal_details=personal_details,
        business_income=50000,
        pension_income=120000,  # 10,000 לחודש
        pension_months_in_year=12
    )
    
    result_with_pension = calculator.calculate_comprehensive_tax(input_with_pension)
    
    print(f"\nתרחיש א' - רק הכנסה מעסק:")
    print(f"  הכנסה מעסק: {input_business_only.business_income:,.2f}")
    print(f"  הכנסה חייבת: {result_business_only.taxable_income:,.2f}")
    print(f"  מס הכנסה: {result_business_only.income_tax:,.2f}")
    print(f"  מס נטו: {result_business_only.net_tax:,.2f}")
    
    print(f"\nתרחיש ב' - הכנסה מעסק + קצבה:")
    print(f"  הכנסה מעסק: {input_with_pension.business_income:,.2f}")
    print(f"  הכנסה מקצבה: {input_with_pension.pension_income:,.2f}")
    print(f"  הכנסה חייבת: {result_with_pension.taxable_income:,.2f}")
    print(f"  מס הכנסה: {result_with_pension.income_tax:,.2f}")
    print(f"  מס נטו: {result_with_pension.net_tax:,.2f}")
    
    print(f"\nהפרש במס הכנסה: {result_with_pension.income_tax - result_business_only.income_tax:,.2f}")
    
    if result_with_pension.income_tax == result_business_only.income_tax:
        print("❌ שגיאה: מס ההכנסה לא השתנה למרות הוספת קצבה!")
        return False
    else:
        print("✅ תוקן: מס ההכנסה השתנה בהתאם להוספת הקצבה")
        return True


def test_exempt_pension_utilization():
    """בדיקה 3: ניצול קצבה פטורה מקיבוע זכויות"""
    print("\n" + "="*80)
    print("בדיקה 3: ניצול קצבה פטורה")
    print("="*80)
    
    personal_details = PersonalDetails(
        birth_date=date(1958, 1, 1),
        marital_status="married",
        num_children=0
    )
    
    calculator = TaxCalculator(tax_year=2025)
    
    # תרחיש א': קצבה ללא פטור
    input_no_exemption = TaxCalculationInput(
        tax_year=2025,
        personal_details=personal_details,
        pension_income=120000,  # 10,000 לחודש
        pension_months_in_year=12,
        exempt_pension_amount=0  # אין קצבה פטורה
    )
    
    result_no_exemption = calculator.calculate_comprehensive_tax(input_no_exemption)
    
    # תרחיש ב': אותה קצבה עם פטור של 2,000 ש"ח לחודש
    input_with_exemption = TaxCalculationInput(
        tax_year=2025,
        personal_details=personal_details,
        pension_income=120000,  # 10,000 לחודש
        pension_months_in_year=12,
        exempt_pension_amount=2000  # 2,000 ש"ח לחודש פטור
    )
    
    result_with_exemption = calculator.calculate_comprehensive_tax(input_with_exemption)
    
    print(f"\nתרחיש א' - ללא קצבה פטורה:")
    print(f"  הכנסה מקצבה: {input_no_exemption.pension_income:,.2f}")
    print(f"  קצבה פטורה: {input_no_exemption.exempt_pension_amount:,.2f}")
    print(f"  הכנסה פטורה: {result_no_exemption.exempt_income:,.2f}")
    print(f"  הכנסה חייבת: {result_no_exemption.taxable_income:,.2f}")
    print(f"  מס נטו: {result_no_exemption.net_tax:,.2f}")
    
    print(f"\nתרחיש ב' - עם קצבה פטורה (2,000 ש\"ח לחודש):")
    print(f"  הכנסה מקצבה: {input_with_exemption.pension_income:,.2f}")
    print(f"  קצבה פטורה חודשית: {input_with_exemption.exempt_pension_amount:,.2f}")
    print(f"  קצבה פטורה שנתית: {input_with_exemption.exempt_pension_amount * 12:,.2f}")
    print(f"  הכנסה פטורה: {result_with_exemption.exempt_income:,.2f}")
    print(f"  הכנסה חייבת: {result_with_exemption.taxable_income:,.2f}")
    print(f"  מס נטו: {result_with_exemption.net_tax:,.2f}")
    
    expected_exemption = input_with_exemption.exempt_pension_amount * 12
    print(f"\nחיסכון במס צפוי: {result_no_exemption.net_tax - result_with_exemption.net_tax:,.2f}")
    
    if result_with_exemption.exempt_income < expected_exemption:
        print(f"❌ שגיאה: הקצבה הפטורה לא נוצלה! צפוי: {expected_exemption:,.2f}, בפועל: {result_with_exemption.exempt_income:,.2f}")
        return False
    else:
        print("✅ תוקן: הקצבה הפטורה מנוצלת כראוי")
        return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("בדיקת 3 תיקונים קריטיים בחישוב המס")
    print("="*80)
    
    results = []
    
    # הרצת הבדיקות
    results.append(("תזמון קצבאות", test_pension_timing_fix()))
    results.append(("שינוי מס על הכנסה מעסק", test_business_income_tax_change()))
    results.append(("ניצול קצבה פטורה", test_exempt_pension_utilization()))
    
    # סיכום
    print("\n" + "="*80)
    print("סיכום תוצאות")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ עבר" if passed else "❌ נכשל"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 כל הבדיקות עברו בהצלחה!")
    else:
        print("\n⚠️ יש בדיקות שנכשלו - נדרש תיקון נוסף")
    
    print("="*80)
