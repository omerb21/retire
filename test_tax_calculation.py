"""בדיקת חישוב מס עבור הכנסת עסק של 20,000 ש"ח בחודש"""

from app.services.tax_calculator import TaxCalculator

# יצירת מחשבון מס
tax_calc = TaxCalculator(tax_year=2024)

# הכנסה חודשית: 20,000 ש"ח
monthly_income = 20000
annual_income = monthly_income * 12  # 240,000 ש"ח

print(f"\n{'='*80}")
print(f"בדיקת חישוב מס עבור הכנסת עסק")
print(f"{'='*80}\n")

print(f"הכנסה חודשית: ₪{monthly_income:,.2f}")
print(f"הכנסה שנתית: ₪{annual_income:,.2f}")
print(f"\n{'-'*80}\n")

# חישוב מס הכנסה
income_tax, breakdown = tax_calc.calculate_income_tax(annual_income)
print(f"מס הכנסה שנתי: ₪{income_tax:,.2f}")
print(f"מס הכנסה חודשי: ₪{income_tax/12:,.2f}")
print(f"\nפירוט לפי מדרגות:")
for b in breakdown:
    print(f"  מדרגה {b.bracket_min:,.0f} - {b.bracket_max or 'ללא תקרה':,.0f}: {b.rate*100:.0f}%")
    print(f"    סכום חייב: ₪{b.taxable_amount:,.2f}")
    print(f"    מס: ₪{b.tax_amount:,.2f}")

# חישוב ביטוח לאומי
ni_tax = tax_calc.calculate_national_insurance(annual_income)
print(f"\nביטוח לאומי שנתי: ₪{ni_tax:,.2f}")
print(f"ביטוח לאומי חודשי: ₪{ni_tax/12:,.2f}")

# חישוב מס בריאות (לא חל על עסק!)
health_tax = tax_calc.calculate_health_tax(annual_income)
print(f"\nמס בריאות שנתי: ₪{health_tax:,.2f}")
print(f"מס בריאות חודשי: ₪{health_tax/12:,.2f}")

# סה"כ מס לעסק (מס הכנסה + ביטוח לאומי בלבד)
total_tax_business = income_tax + ni_tax
print(f"\n{'-'*80}")
print(f"סה״כ מס לעסק (מס הכנסה + ביטוח לאומי):")
print(f"  שנתי: ₪{total_tax_business:,.2f}")
print(f"  חודשי: ₪{total_tax_business/12:,.2f}")

# סה"כ מס לשכיר (מס הכנסה + ביטוח לאומי + מס בריאות)
total_tax_salary = income_tax + ni_tax + health_tax
print(f"\nסה״כ מס לשכיר (מס הכנסה + ביטוח לאומי + מס בריאות):")
print(f"  שנתי: ₪{total_tax_salary:,.2f}")
print(f"  חודשי: ₪{total_tax_salary/12:,.2f}")

print(f"\n{'='*80}\n")
