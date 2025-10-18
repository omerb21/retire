"""
Check education fund details
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'retire.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Find education fund
cursor.execute("""
    SELECT id, fund_name, fund_type, tax_treatment 
    FROM pension_funds 
    WHERE fund_name LIKE '%השתלמות%'
""")
rows = cursor.fetchall()

print("📋 Education funds found:")
for row in rows:
    print(f"  ID={row[0]}")
    print(f"  Name={row[1]}")
    print(f"  Type={row[2]}")
    print(f"  TaxTreatment={row[3]}")
    print(f"  Should be: exempt (if 'השתלמות' in type or name)")
    print()

# Update education fund to exempt
if rows:
    print("🔧 Updating education funds to exempt...")
    for row in rows:
        cursor.execute(
            "UPDATE pension_funds SET tax_treatment = 'exempt' WHERE id = ?",
            (row[0],)
        )
    conn.commit()
    print(f"✅ Updated {len(rows)} education funds to exempt")

conn.close()
