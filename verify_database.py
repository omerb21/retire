"""
Verify database has tax_treatment column
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'retire.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check columns
cursor.execute("PRAGMA table_info(pension_funds)")
columns = cursor.fetchall()

print("📊 pension_funds columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Check if tax_treatment exists
has_tax_treatment = any(col[1] == 'tax_treatment' for col in columns)
print(f"\n{'✅' if has_tax_treatment else '❌'} tax_treatment column exists: {has_tax_treatment}")

# Test data
if has_tax_treatment:
    cursor.execute("SELECT id, fund_name, tax_treatment FROM pension_funds LIMIT 5")
    rows = cursor.fetchall()
    print(f"\n📋 Sample data ({len(rows)} records):")
    for row in rows:
        print(f"  - ID={row[0]}, Name={row[1]}, TaxTreatment={row[2]}")

conn.close()
