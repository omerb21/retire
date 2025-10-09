"""
Script to add deduction_file column to pension_funds table
"""
import sqlite3
import os

# Path to database
db_path = "retire.db"

def add_deduction_file_column():
    """Add deduction_file column to pension_funds table if it doesn't exist"""
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(pension_funds)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'deduction_file' not in columns:
            # Add the column
            cursor.execute("ALTER TABLE pension_funds ADD COLUMN deduction_file VARCHAR(200)")
            conn.commit()
            print("Successfully added deduction_file column to pension_funds table")
        else:
            print("deduction_file column already exists")
            
    except Exception as e:
        print(f"Error adding column: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_deduction_file_column()
