"""בדיקת חישוב מס הכנסה - לקוח 1 (8,333 לחודש)"""

from app.services.tax_calculator import TaxCalculator

print(f"\n{'='*80}")
print(f"בדיקת חישוב מס הכנסה - לקוח 1")
print(f"{'='*80}\n")

# יצירת מחשבון מס לשנת 2025
tax_calc = TaxCalculator(tax_year=2025)

# נתוני לקוח 1: 8,333 לחודש = 99,996 לשנה
monthly_income = 8333
annual_income = monthly_income * 12
tax_credit_points = 2.25

print(f"נתוני הקלט:")
print(f"  הכנסה חודשית: ₪{monthly_income:,.2f}")
print(f"  הכנסה שנתית: ₪{annual_income:,.2f}")
print(f"  נקודות זיכוי: {tax_credit_points}")
print(f"\n{'-'*80}\n")

# חישוב מס לפני זיכויים
tax_before_credits, breakdown = tax_calc.calculate_income_tax(annual_income)

print(f"חישוב מס לפני זיכויים:")
for item in breakdown:
    print(f"  מדרגה {item.bracket_min:,.0f}-{item.bracket_max if item.bracket_max else 'ומעלה':>10}: "
          f"₪{item.taxable_amount:>10,.2f} × {item.rate*100:>4.0f}% = ₪{item.tax_amount:>10,.2f}")
print(f"\n  סה\"כ מס לפני זיכויים: ₪{tax_before_credits:,.2f}")

# חישוב זיכוי
tax_credit_value = 2904  # ערך נקודת זיכוי לשנת 2025
total_credit = tax_credit_points * tax_credit_value
print(f"\n{'-'*80}\n")
print(f"זיכוי ממס:")
print(f"  {tax_credit_points} נקודות × ₪{tax_credit_value:,.0f} = ₪{total_credit:,.2f}")

# מס סופי
final_tax = max(0, tax_before_credits - total_credit)
monthly_tax = final_tax / 12

print(f"\n{'-'*80}\n")
print(f"תוצאה סופית:")
print(f"  מס שנתי לאחר זיכויים: ₪{final_tax:,.2f}")
print(f"  מס חודשי: ₪{monthly_tax:,.2f}")
print(f"  שיעור מס אפקטיבי: {(final_tax/annual_income)*100:.2f}%")

print(f"\n{'-'*80}\n")
print(f"בדיקה ידנית (לפי החישוב הנכון):")
print(f"  מדרגה 1 (0-84,120): 84,120 × 10% = 8,412.00")
print(f"  מדרגה 2 (84,121-99,996): 15,876 × 14% = 2,222.64")
print(f"  סה\"כ מס לפני זיכויים: 10,634.64")
print(f"  זיכוי: 2.25 × 2,904 = 6,534.00")
print(f"  מס לאחר זיכויים: 10,634.64 - 6,534.00 = 4,100.64")
print(f"  מס חודשי: 4,100.64 / 12 = 341.72")

print(f"\n{'='*80}\n")
