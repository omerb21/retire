"""Fix tax_rate constraint in SQLite database"""
import sqlite3
import os

# Path to database
db_path = os.path.join(os.path.dirname(__file__), 'retire.db')

print(f"Connecting to database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n1. Creating backup of additional_income table...")
    cursor.execute("""
        CREATE TABLE additional_income_backup AS 
        SELECT * FROM additional_income
    """)
    print("✓ Backup created")
    
    print("\n2. Dropping old additional_income table...")
    cursor.execute("DROP TABLE additional_income")
    print("✓ Old table dropped")
    
    print("\n3. Creating new additional_income table with updated constraint...")
    cursor.execute("""
        CREATE TABLE additional_income (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            description VARCHAR(255),
            amount NUMERIC(12, 2) NOT NULL,
            frequency VARCHAR(20) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE,
            indexation_method VARCHAR(20) NOT NULL DEFAULT 'none',
            fixed_rate NUMERIC(5, 4),
            tax_treatment VARCHAR(20) NOT NULL DEFAULT 'taxable',
            tax_rate NUMERIC(5, 2),
            remarks VARCHAR(500),
            FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE,
            CHECK (amount > 0),
            CHECK (end_date IS NULL OR end_date >= start_date),
            CHECK (indexation_method != 'fixed' OR fixed_rate IS NOT NULL),
            CHECK (tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL),
            CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
            CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 99))
        )
    """)
    print("✓ New table created with tax_rate constraint: 0-99")
    
    print("\n4. Restoring data from backup...")
    cursor.execute("""
        INSERT INTO additional_income 
        SELECT * FROM additional_income_backup
    """)
    print("✓ Data restored")
    
    print("\n5. Dropping backup table...")
    cursor.execute("DROP TABLE additional_income_backup")
    print("✓ Backup table dropped")
    
    print("\n6. Creating index...")
    cursor.execute("CREATE INDEX ix_additional_income_client_id ON additional_income (client_id)")
    print("✓ Index created")
    
    conn.commit()
    print("\n✅ SUCCESS! Database updated successfully!")
    print("Tax rate now accepts values from 0 to 99 (percentage)")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nRolling back changes...")
    conn.rollback()
    
finally:
    conn.close()
    print("\nDatabase connection closed.")
