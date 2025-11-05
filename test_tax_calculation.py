"""בדיקת חישוב מס משולב על פיצויים - לקוח 5"""

from decimal import Decimal
from app.services.capital_asset import CapitalAssetService

# יצירת service
service = CapitalAssetService()

print(f"\n{'='*80}")
print(f"בדיקת חישוב מס משולב על פיצויים - לקוח 5")
print(f"{'='*80}\n")

# נתונים מלקוח 5
exempt_amount = Decimal('371938')
taxable_amount = Decimal('713785')
spread_years = 6

print(f"מענק פטור: ₪{exempt_amount:,.2f}")
print(f"מענק חייב: ₪{taxable_amount:,.2f}")
print(f"פריסה: {spread_years} שנים")
print(f"\n{'-'*80}\n")

# חישוב מס משולב
result = service.calculate_combined_severance_tax(
    exempt_amount=exempt_amount,
    taxable_amount=taxable_amount,
    spread_years=spread_years,
    annual_regular_income=Decimal('0')
)

print(f"\nתוצאות חישוב:")
print(f"  פטור לשנה: ₪{result['exempt_annual']:,.2f}")
print(f"  חייב לשנה: ₪{result['taxable_annual']:,.2f}")
print(f"  סה\"כ לשנה: ₪{result['total_annual']:,.2f}")
print(f"\n  מס שנתי: ₪{result['yearly_taxes'][0]:,.2f}")
print(f"  סה\"כ מס ל-{spread_years} שנים: ₪{result['total_tax']:,.2f}")
print(f"\n  סה\"כ ברוטו: ₪{exempt_amount + taxable_amount:,.2f}")
print(f"  סה\"כ נטו: ₪{exempt_amount + taxable_amount - result['total_tax']:,.2f}")

print(f"\n{'-'*80}")
print(f"\nבדיקה ידנית:")
print(f"  הכנסה שנתית: {result['total_annual']:,.2f}")
print(f"  מדרגה 1 (עד 84,000): 84,000 × 14% = 11,760")
print(f"  מדרגה 2 (84,001-{result['total_annual']:,.2f}): {result['total_annual'] - Decimal('84000'):,.2f} × 20% = {(result['total_annual'] - Decimal('84000')) * Decimal('0.20'):,.2f}")
print(f"  סה\"כ מס שנתי: {Decimal('11760') + (result['total_annual'] - Decimal('84000')) * Decimal('0.20'):,.2f}")
print(f"  סה\"כ מס ל-{spread_years} שנים: {(Decimal('11760') + (result['total_annual'] - Decimal('84000')) * Decimal('0.20')) * spread_years:,.2f}")

print(f"\n{'='*80}\n")
