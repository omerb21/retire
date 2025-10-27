#!/usr/bin/env python
"""Check pension_fund_coefficient data"""
from app.database import engine
from sqlalchemy import text

print("Sample rows from pension_fund_coefficient:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, fund_name, survivors_option, sex, retirement_age, spouse_age_diff, base_coefficient, adjust_percent
        FROM pension_fund_coefficient
        LIMIT 5
    """))
    for row in result:
        print(f"  {row}")

print("\n\nSearching for: sex='זכר', retirement_age=67, survivors_option='זקנה + שארים תקנוני', spouse_age_diff=0")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, fund_name, survivors_option, sex, retirement_age, spouse_age_diff, base_coefficient, adjust_percent
        FROM pension_fund_coefficient
        WHERE sex = 'זכר'
          AND retirement_age = 67
          AND survivors_option = 'זקנה + שארים תקנוני'
          AND spouse_age_diff = 0
        LIMIT 5
    """))
    rows = result.fetchall()
    if rows:
        for row in rows:
            print(f"  ✅ Found: {row}")
    else:
        print("  ❌ No rows found!")

print("\n\nAll unique survivors_option values:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT survivors_option
        FROM pension_fund_coefficient
    """))
    for row in result:
        print(f"  - '{row[0]}'")

print("\n\nAll unique sex values:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT sex
        FROM pension_fund_coefficient
    """))
    for row in result:
        print(f"  - '{row[0]}'")

print("\n\nAll unique retirement_age values (first 20):")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT retirement_age
        FROM pension_fund_coefficient
        ORDER BY retirement_age
        LIMIT 20
    """))
    for row in result:
        print(f"  - {row[0]}")
