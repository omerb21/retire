#!/usr/bin/env python
"""Check spouse_age_diff values in table"""
from app.database import engine
from sqlalchemy import text

print("All unique spouse_age_diff values:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT spouse_age_diff
        FROM pension_fund_coefficient
        ORDER BY spouse_age_diff
    """))
    diffs = [row[0] for row in result.fetchall()]
    print(f"  {diffs}")

print("\nSearching for spouse_age_diff=0:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT COUNT(*) FROM pension_fund_coefficient
        WHERE spouse_age_diff = 0
    """))
    count = result.scalar()
    print(f"  Found {count} rows")

print("\nSearching for spouse_age_diff=-20:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT COUNT(*) FROM pension_fund_coefficient
        WHERE spouse_age_diff = -20
    """))
    count = result.scalar()
    print(f"  Found {count} rows")
