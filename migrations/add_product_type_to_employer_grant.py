"""
Migration: Add product_type to employer_grant table
Date: 2025-10-27
Description: Add product_type field to link grants to specific product types for correct annuity coefficient calculation
"""
import sqlite3

def run_migration():
    # Connect to the database
    conn = sqlite3.connect('retire.db')
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(employer_grant)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add product_type if it doesn't exist
        if 'product_type' not in columns:
            print("Adding product_type column...")
            cursor.execute("ALTER TABLE employer_grant ADD COLUMN product_type TEXT")
            print("✓ Added product_type column")
        else:
            print("✓ product_type column already exists")
        
        # Commit changes
        conn.commit()
        print("\nMigration completed successfully!")
        
        # Show the updated table structure
        print("\nUpdated table structure:")
        cursor.execute("PRAGMA table_info(employer_grant)")
        for column in cursor.fetchall():
            print(f"  {column[1]}: {column[2]}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
