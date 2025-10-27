import sqlite3

def run_migration():
    # Connect to the database
    conn = sqlite3.connect('retire.db')
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(employer_grant)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add plan_name if it doesn't exist
        if 'plan_name' not in columns:
            print("Adding plan_name column...")
            cursor.execute("ALTER TABLE employer_grant ADD COLUMN plan_name TEXT")
            print("✓ Added plan_name column")
        else:
            print("✓ plan_name column already exists")
        
        # Add plan_start_date if it doesn't exist
        if 'plan_start_date' not in columns:
            print("Adding plan_start_date column...")
            cursor.execute("ALTER TABLE employer_grant ADD COLUMN plan_start_date DATE")
            print("✓ Added plan_start_date column")
        else:
            print("✓ plan_start_date column already exists")
        
        # Commit changes
        conn.commit()
        print("\nMigration completed successfully!")
        
        # Show the updated table structure
        print("\nUpdated table structure:")
        cursor.execute("PRAGMA table_info(employer_grant)")
        for column in cursor.fetchall():
            print(f"- {column[1]} ({column[2]})")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting migration...\n")
    run_migration()
