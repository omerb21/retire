#!/usr/bin/env python
"""Test the coefficient calculation"""
from datetime import date
from app.services.annuity_coefficient_service import get_annuity_coefficient

# Test case: קרן השתלמות (קרן פנסיה)
result = get_annuity_coefficient(
    product_type='קרן השתלמות',
    start_date=date(2020, 1, 1),
    gender='זכר',
    retirement_age=67,
    birth_date=date(1957, 10, 2),
    pension_start_date=date(2025, 1, 1)
)

print("Test: קרן השתלמות, זכר, גיל 67")
print(f"  Factor: {result['factor_value']}")
print(f"  Source: {result['source_table']}")
print(f"  Keys: {result['source_keys']}")

if result['factor_value'] != 200.0:
    print("  ✅ SUCCESS - Got real coefficient, not default 200!")
else:
    print("  ❌ FAILED - Still getting default 200")
