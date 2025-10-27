#!/usr/bin/env python
"""Test termination pension creation with dynamic coefficient"""
from datetime import date
from app.services.annuity_coefficient_service import get_annuity_coefficient

# Test parameters
product_type = 'קופת גמל'
start_date = date(2010, 1, 1)
gender = 'זכר'
retirement_age = 67
birth_date = date(1957, 10, 2)
pension_start_date = date(2025, 1, 1)

print("Testing dynamic coefficient for termination pension:")
print("=" * 60)
print(f"Product Type: {product_type}")
print(f"Start Date: {start_date}")
print(f"Gender: {gender}")
print(f"Retirement Age: {retirement_age}")
print(f"Birth Date: {birth_date}")
print(f"Pension Start Date: {pension_start_date}")
print()

try:
    result = get_annuity_coefficient(
        product_type=product_type,
        start_date=start_date,
        gender=gender,
        retirement_age=retirement_age,
        survivors_option='תקנוני',
        spouse_age_diff=0,
        birth_date=birth_date,
        pension_start_date=pension_start_date
    )
    
    print("✅ SUCCESS!")
    print(f"Annuity Factor: {result['factor_value']}")
    print(f"Source Table: {result['source_table']}")
    print(f"Source Keys: {result['source_keys']}")
    print(f"Notes: {result['notes']}")
    print()
    
    # Calculate pension amount
    severance_amount = 100000  # Example
    pension_amount = severance_amount / result['factor_value']
    print(f"Example: Severance ₪{severance_amount:,.0f} → Pension ₪{pension_amount:,.0f}/month")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
