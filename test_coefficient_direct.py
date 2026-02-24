"""
Direct test of get_annuity_coefficient for ages 70 and 71
Run 15 - Verify coefficient data differs by age
"""

from datetime import date
from app.services.annuity_coefficient import get_annuity_coefficient

print("=" * 80)
print("🧪 DIRECT TEST: get_annuity_coefficient for ages 70 vs 71")
print("=" * 80)

birth = date(1958, 1, 1)  # גיל 70 ב-2028, 71 ב-2029
policy_start = date(2010, 1, 1)

print("\n📋 Test Parameters:")
print(f"  Birth Date: {birth}")
print(f"  Policy Start: {policy_start}")
print(f"  Product Type: קרן פנסיה")
print(f"  Gender: זכר")

print("\n" + "=" * 80)
print("🔵 TEST 1: Age 70 (Retirement in 2028)")
print("=" * 80)

coeff70 = get_annuity_coefficient(
    product_type="קרן פנסיה",
    start_date=policy_start,
    gender="זכר",
    retirement_age=70,
    target_year=2028,
    birth_date=birth,
    pension_start_date=date(2028, 1, 1),
)

print(f"\n✅ Result for Age 70:")
print(f"  Factor Value: {coeff70.get('factor_value', 'N/A')}")
print(f"  Source Table: {coeff70.get('source_table', 'N/A')}")
print(f"  Source Keys: {coeff70.get('source_keys', {})}")
print(f"  Notes: {coeff70.get('notes', 'N/A')}")

print("\n" + "=" * 80)
print("🔵 TEST 2: Age 71 (Retirement in 2029)")
print("=" * 80)

coeff71 = get_annuity_coefficient(
    product_type="קרן פנסיה",
    start_date=policy_start,
    gender="זכר",
    retirement_age=71,
    target_year=2029,
    birth_date=birth,
    pension_start_date=date(2029, 1, 1),
)

print(f"\n✅ Result for Age 71:")
print(f"  Factor Value: {coeff71.get('factor_value', 'N/A')}")
print(f"  Source Table: {coeff71.get('source_table', 'N/A')}")
print(f"  Source Keys: {coeff71.get('source_keys', {})}")
print(f"  Notes: {coeff71.get('notes', 'N/A')}")

print("\n" + "=" * 80)
print("📊 COMPARISON")
print("=" * 80)

factor70 = coeff70.get("factor_value", 0)
factor71 = coeff71.get("factor_value", 0)

print(f"\n  Age 70 Factor: {factor70}")
print(f"  Age 71 Factor: {factor71}")
print(f"  Difference: {factor70 - factor71:.2f}")
print(f"  % Change: {((factor71 - factor70) / factor70 * 100):.2f}%")

if factor70 == factor71:
    print("\n❌ PROBLEM: Factors are IDENTICAL (should differ by age)")
elif factor71 < factor70:
    print("\n✅ CORRECT: Factor at 71 is LOWER than at 70")
    print("   → Higher pension expected at age 71 for same balance")
else:
    print("\n⚠️ UNEXPECTED: Factor at 71 is HIGHER than at 70")

print("\n" + "=" * 80)
print("🧮 PENSION CALCULATION EXAMPLE")
print("=" * 80)

test_balance = 100000  # ₪100,000 balance
pension70 = test_balance / factor70 if factor70 > 0 else 0
pension71 = test_balance / factor71 if factor71 > 0 else 0

print(f"\n  For balance of ₪{test_balance:,.0f}:")
print(f"  Age 70 Pension: ₪{pension70:,.2f}/month")
print(f"  Age 71 Pension: ₪{pension71:,.2f}/month")
print(f"  Difference: ₪{pension71 - pension70:,.2f}/month")

print("\n" + "=" * 80)
