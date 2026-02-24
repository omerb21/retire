"""
Migration script to add original_principal column to capital_assets table
Run this script directly: python migrations/add_original_principal_to_capital_assets.py
"""

import sqlite3
import os


def run_migration():
    # Get the database path
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "retire.db")

    print(f"🔍 Connecting to database: {db_path}")

    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(capital_assets)")
        columns = [row[1] for row in cursor.fetchall()]

        if "original_principal" in columns:
            print(
                "✅ Column 'original_principal' already exists in capital_assets table"
            )
            conn.close()
            return True

        # Add the column
        print("📝 Adding 'original_principal' column to capital_assets table...")
        cursor.execute("""
            ALTER TABLE capital_assets 
            ADD COLUMN original_principal REAL
        """)

        conn.commit()
        print("✅ Successfully added 'original_principal' column")

        # Verify the column was added
        cursor.execute("PRAGMA table_info(capital_assets)")
        columns = [row[1] for row in cursor.fetchall()]

        if "original_principal" in columns:
            print("✅ Verification successful - column exists")
        else:
            print("❌ Verification failed - column not found")
            return False

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add original_principal to capital_assets")
    print("=" * 60)
    success = run_migration()
    print("=" * 60)
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
    print("=" * 60)
