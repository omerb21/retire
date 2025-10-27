#!/usr/bin/env python
"""Test termination API with dynamic coefficient"""
from datetime import date
from app.services.annuity_coefficient_service import get_annuity_coefficient

# Simulate termination parameters
termination_date = date(2025, 12, 1)
start_date = date(2010, 1, 1)
birth_date = date(1957, 10, 2)
gender = 'זכר'

print("Testing dynamic coefficient for termination API:")
print("=" * 60)
print(f"Termination Date: {termination_date}")
print(f"Employment Start: {start_date}")
print(f"Birth Date: {birth_date}")
print(f"Gender: {gender}")
print()

try:
    result = get_annuity_coefficient(
        product_type='קופת גמל',
        start_date=start_date,
        gender=gender,
        retirement_age=67,
        survivors_option='תקנוני',
        spouse_age_diff=0,
        birth_date=birth_date,
        pension_start_date=termination_date
    )
    
    print("✅ SUCCESS!")
    print(f"Annuity Factor: {result['factor_value']}")
    print(f"Source Table: {result['source_table']}")
    print()
    
    # Calculate pension amounts
    exempt_amount = 53833.0
    taxable_amount = 134793.0
    
    exempt_pension = exempt_amount / result['factor_value']
    taxable_pension = taxable_amount / result['factor_value']
    
    print(f"Exempt Amount: ₪{exempt_amount:,.0f} → Pension: ₪{exempt_pension:,.2f}/month")
    print(f"Taxable Amount: ₪{taxable_amount:,.0f} → Pension: ₪{taxable_pension:,.2f}/month")
    print()
    print(f"OLD (factor=200): ₪{exempt_amount/200:,.2f} + ₪{taxable_amount/200:,.2f} = ₪{(exempt_amount+taxable_amount)/200:,.2f}/month")
    print(f"NEW (factor={result['factor_value']}): ₪{exempt_pension:,.2f} + ₪{taxable_pension:,.2f} = ₪{exempt_pension+taxable_pension:,.2f}/month")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
