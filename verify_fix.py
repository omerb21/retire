import sqlite3
import sys

db_path = 'retire.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get table schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='additional_income'")
    result = cursor.fetchone()
    
    if result:
        schema = result[0]
        print("Current schema for additional_income table:")
        print(schema)
        print("\n" + "="*80)
        
        # Check if the new constraint exists
        if "tax_rate >= 0 AND tax_rate <= 99" in schema:
            print("\n✅ SUCCESS! Constraint updated to 0-99")
        elif "tax_rate >= 0 AND tax_rate <= 1" in schema:
            print("\n❌ FAILED! Still using old constraint (0-1)")
        else:
            print("\n⚠️ WARNING! Could not find tax_rate constraint")
    else:
        print("❌ Table 'additional_income' not found!")
    
    conn.close()
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
