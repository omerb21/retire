#!/usr/bin/env python
"""Test direct database query for pension fund coefficient"""
from app.database import engine
from sqlalchemy import text

print("Testing direct query to pension_fund_coefficient table:")
print("=" * 60)

# Test 1: Search with תקנוני
print("\n1️⃣ Searching with survivors_option='תקנוני':")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, fund_name, survivors_option, sex, retirement_age, spouse_age_diff, base_coefficient, adjust_percent
        FROM pension_fund_coefficient
        WHERE sex = 'זכר'
          AND retirement_age = 68
          AND survivors_option = 'תקנוני'
          AND spouse_age_diff = 0
        LIMIT 1
    """))
    row = result.fetchone()
    if row:
        print(f"  ✅ FOUND: {row}")
        factor = row[6] * row[7]  # base_coefficient * adjust_percent
        print(f"  Factor = {row[6]} * {row[7]} = {factor}")
    else:
        print("  ❌ NOT FOUND")

# Test 2: Check what values actually exist for age 68
print("\n2️⃣ All rows for sex='זכר', retirement_age=68, survivors_option='תקנוני':")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT spouse_age_diff, base_coefficient, adjust_percent
        FROM pension_fund_coefficient
        WHERE sex = 'זכר'
          AND retirement_age = 68
          AND survivors_option = 'תקנוני'
        ORDER BY spouse_age_diff
        LIMIT 10
    """))
    rows = result.fetchall()
    if rows:
        for row in rows:
            factor = row[1] * row[2]
            print(f"  spouse_age_diff={row[0]}: {row[1]} * {row[2]} = {factor}")
    else:
        print("  ❌ NO ROWS FOUND")

# Test 3: Check if there are any rows at all for age 68
print("\n3️⃣ Count of rows for retirement_age=68:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT COUNT(*) FROM pension_fund_coefficient
        WHERE retirement_age = 68
    """))
    count = result.scalar()
    print(f"  Total rows: {count}")

# Test 4: Check all ages available
print("\n4️⃣ All available retirement_age values:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT retirement_age
        FROM pension_fund_coefficient
        ORDER BY retirement_age
    """))
    ages = [row[0] for row in result.fetchall()]
    print(f"  Ages: {ages}")
