"""
Script to add tax_treatment column to pension_funds table (SQLite version)
"""
import sqlite3
import os

# Get database path
db_path = os.path.join(os.path.dirname(__file__), 'retire.db')

print(f"Connecting to database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if column exists
    cursor.execute("PRAGMA table_info(pension_funds)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'tax_treatment' in columns:
        print("⚠️ Column tax_treatment already exists")
    else:
        # Add the column with default value
        cursor.execute("""
            ALTER TABLE pension_funds 
            ADD COLUMN tax_treatment TEXT NOT NULL DEFAULT 'taxable'
        """)
        conn.commit()
        print("✅ Added tax_treatment column to pension_funds table")
    
    # Verify
    cursor.execute("PRAGMA table_info(pension_funds)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Current columns: {columns}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    conn.close()
