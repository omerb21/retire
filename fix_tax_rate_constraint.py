"""Fix tax_rate constraint in additional_income table"""
from app.database import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        # Drop old constraint
        try:
            conn.execute(text('ALTER TABLE additional_income DROP CONSTRAINT check_valid_tax_rate'))
            print("✓ Dropped old constraint")
        except Exception as e:
            print(f"Note: Could not drop constraint (might not exist): {e}")
        
        # Add new constraint
        conn.execute(text('''
            ALTER TABLE additional_income 
            ADD CONSTRAINT check_valid_tax_rate 
            CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 99))
        '''))
        print("✓ Added new constraint (0-99)")
        
        conn.commit()
        print("\n✅ Database updated successfully!")
        print("Tax rate now accepts values from 0 to 99 (percentage)")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nNote: If using SQLite, constraints cannot be modified.")
    print("You may need to recreate the table or use a different approach.")
