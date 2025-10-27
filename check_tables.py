#!/usr/bin/env python
"""Check what tables exist in the database"""
from app.database import engine
from sqlalchemy import inspect, text

inspector = inspect(engine)
tables = inspector.get_table_names()

print("All tables in database:")
for t in sorted(tables):
    print(f"  - {t}")

print("\nTables related to coefficients:")
for t in sorted(tables):
    if 'coefficient' in t.lower() or 'pension' in t.lower():
        print(f"  - {t}")
        # Get columns
        columns = inspector.get_columns(t)
        for col in columns:
            print(f"      - {col['name']}: {col['type']}")

# Try to query pension_fund_coefficient
print("\n\nTrying to query pension_fund_coefficient:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM pension_fund_coefficient"))
        count = result.scalar()
        print(f"✅ Table exists, {count} rows")
except Exception as e:
    print(f"❌ Error: {e}")

# Try to query policy_generation_coefficient
print("\nTrying to query policy_generation_coefficient:")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM policy_generation_coefficient"))
        count = result.scalar()
        print(f"✅ Table exists, {count} rows")
except Exception as e:
    print(f"❌ Error: {e}")
