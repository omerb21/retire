"""
Migration script to fix capital_asset check constraint.
Allows current_value to be 0 (needed for commutations).

Run this script to update the database constraint.
"""

import sqlite3
import os

# Path to database
DB_PATH = os.path.join(os.path.dirname(__file__), "retire.db")

def migrate():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Starting migration...")
        
        # Step 1: Create a new table with the correct constraint
        print("1. Creating temporary table with new constraint...")
        cursor.execute("""
            CREATE TABLE capital_assets_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                asset_name VARCHAR(255),
                asset_type VARCHAR(50) NOT NULL,
                description VARCHAR(255),
                current_value DECIMAL(15, 2) NOT NULL,
                monthly_income DECIMAL(15, 2),
                rental_income DECIMAL(15, 2),
                monthly_rental_income DECIMAL(15, 2),
                annual_return_rate DECIMAL(5, 4) NOT NULL,
                payment_frequency VARCHAR(20) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                indexation_method VARCHAR(20) NOT NULL DEFAULT 'none',
                fixed_rate DECIMAL(5, 4),
                tax_treatment VARCHAR(20) NOT NULL DEFAULT 'taxable',
                tax_rate DECIMAL(5, 4),
                spread_years INTEGER,
                remarks VARCHAR(500),
                conversion_source VARCHAR(1000),
                FOREIGN KEY (client_id) REFERENCES clients(id),
                CHECK (current_value >= 0),
                CHECK (annual_return_rate >= 0),
                CHECK (end_date IS NULL OR end_date >= start_date),
                CHECK (indexation_method != 'fixed' OR fixed_rate IS NOT NULL),
                CHECK (tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL)
            )
        """)
        
        # Step 2: Copy data from old table to new table
        print("2. Copying data from old table...")
        cursor.execute("""
            INSERT INTO capital_assets_new 
            SELECT * FROM capital_assets
        """)
        
        # Step 3: Drop old table
        print("3. Dropping old table...")
        cursor.execute("DROP TABLE capital_assets")
        
        # Step 4: Rename new table to original name
        print("4. Renaming new table...")
        cursor.execute("ALTER TABLE capital_assets_new RENAME TO capital_assets")
        
        # Commit changes
        conn.commit()
        print("✅ Migration completed successfully!")
        print("   - current_value can now be 0 (needed for commutations)")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
