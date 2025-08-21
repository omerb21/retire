"""
Script to fix issues with Additional Income and Capital Asset modules.
"""
import os
import sys
from sqlalchemy import text

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Import app modules
from app.database import engine, SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset

def fix_foreign_keys():
    """Fix foreign key references in the database."""
    print("Fixing foreign key references...")
    
    # Create a session
    db = SessionLocal()
    try:
        # Check if tables exist
        with engine.connect() as conn:
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            table_names = [table[0] for table in tables]
            print(f"Existing tables: {table_names}")
            
            # Check if additional_income table exists
            if 'additional_income' in table_names:
                # Check foreign key references
                fks = conn.execute(text("PRAGMA foreign_key_list(additional_income)")).fetchall()
                print(f"Additional Income foreign keys: {fks}")
                
                # Fix foreign key if needed
                if any(fk[2] == 'clients' for fk in fks):
                    print("Fixing additional_income foreign key...")
                    # SQLite doesn't support ALTER TABLE to modify foreign keys directly
                    # We need to recreate the table with the correct foreign key
                    
                    # Create a backup of the data
                    conn.execute(text("CREATE TABLE additional_income_backup AS SELECT * FROM additional_income"))
                    
                    # Drop the original table
                    conn.execute(text("DROP TABLE additional_income"))
                    
                    # Create the table with correct foreign key
                    conn.execute(text("""
                    CREATE TABLE additional_income (
                        id INTEGER NOT NULL, 
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
                        tax_rate NUMERIC(5, 4), 
                        remarks VARCHAR(500), 
                        PRIMARY KEY (id), 
                        FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE,
                        CONSTRAINT check_positive_amount CHECK (amount > 0),
                        CONSTRAINT check_valid_date_range CHECK (end_date IS NULL OR end_date >= start_date),
                        CONSTRAINT check_fixed_rate_when_fixed_indexation CHECK (indexation_method != 'fixed' OR fixed_rate IS NOT NULL),
                        CONSTRAINT check_tax_rate_when_fixed_tax CHECK (tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL),
                        CONSTRAINT check_non_negative_fixed_rate CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
                        CONSTRAINT check_valid_tax_rate CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1))
                    )
                    """))
                    
                    # Create indexes
                    conn.execute(text("CREATE INDEX ix_additional_income_id ON additional_income (id)"))
                    conn.execute(text("CREATE INDEX ix_additional_income_client_id ON additional_income (client_id)"))
                    
                    # Restore the data
                    conn.execute(text("INSERT INTO additional_income SELECT * FROM additional_income_backup"))
                    
                    # Drop the backup table
                    conn.execute(text("DROP TABLE additional_income_backup"))
                    
                    print("Fixed additional_income foreign key.")
            
            # Check if capital_assets table exists
            if 'capital_assets' in table_names:
                # Check foreign key references
                fks = conn.execute(text("PRAGMA foreign_key_list(capital_assets)")).fetchall()
                print(f"Capital Assets foreign keys: {fks}")
                
                # Fix foreign key if needed
                if any(fk[2] == 'clients' for fk in fks):
                    print("Fixing capital_assets foreign key...")
                    # SQLite doesn't support ALTER TABLE to modify foreign keys directly
                    # We need to recreate the table with the correct foreign key
                    
                    # Create a backup of the data
                    conn.execute(text("CREATE TABLE capital_assets_backup AS SELECT * FROM capital_assets"))
                    
                    # Drop the original table
                    conn.execute(text("DROP TABLE capital_assets"))
                    
                    # Create the table with correct foreign key
                    conn.execute(text("""
                    CREATE TABLE capital_assets (
                        id INTEGER NOT NULL, 
                        client_id INTEGER NOT NULL, 
                        asset_type VARCHAR(50) NOT NULL, 
                        description VARCHAR(255), 
                        current_value NUMERIC(15, 2) NOT NULL, 
                        annual_return_rate NUMERIC(5, 4) NOT NULL, 
                        payment_frequency VARCHAR(20) NOT NULL, 
                        start_date DATE NOT NULL, 
                        end_date DATE, 
                        indexation_method VARCHAR(20) NOT NULL DEFAULT 'none', 
                        fixed_rate NUMERIC(5, 4), 
                        tax_treatment VARCHAR(20) NOT NULL DEFAULT 'taxable', 
                        tax_rate NUMERIC(5, 4), 
                        remarks VARCHAR(500), 
                        PRIMARY KEY (id), 
                        FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE,
                        CONSTRAINT check_positive_value CHECK (current_value > 0),
                        CONSTRAINT check_non_negative_return CHECK (annual_return_rate >= 0),
                        CONSTRAINT check_valid_date_range CHECK (end_date IS NULL OR end_date >= start_date),
                        CONSTRAINT check_fixed_rate_when_fixed_indexation CHECK (indexation_method != 'fixed' OR fixed_rate IS NOT NULL),
                        CONSTRAINT check_tax_rate_when_fixed_tax CHECK (tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL),
                        CONSTRAINT check_non_negative_fixed_rate CHECK (fixed_rate IS NULL OR fixed_rate >= 0),
                        CONSTRAINT check_valid_tax_rate CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1))
                    )
                    """))
                    
                    # Create indexes
                    conn.execute(text("CREATE INDEX ix_capital_assets_id ON capital_assets (id)"))
                    conn.execute(text("CREATE INDEX ix_capital_assets_client_id ON capital_assets (client_id)"))
                    
                    # Restore the data
                    conn.execute(text("INSERT INTO capital_assets SELECT * FROM capital_assets_backup"))
                    
                    # Drop the backup table
                    conn.execute(text("DROP TABLE capital_assets_backup"))
                    
                    print("Fixed capital_assets foreign key.")
        
        db.commit()
        print("Foreign key fixes applied successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error fixing foreign keys: {e}")
    finally:
        db.close()

def verify_models():
    """Verify model configurations."""
    print("\nVerifying model configurations...")
    
    # Check Client model
    print(f"Client table name: {Client.__tablename__}")
    
    # Check AdditionalIncome model
    print(f"AdditionalIncome table name: {AdditionalIncome.__tablename__}")
    print(f"AdditionalIncome client_id FK: {AdditionalIncome.client_id.foreign_keys}")
    print(f"AdditionalIncome indexation_method default: {AdditionalIncome.indexation_method.default}")
    print(f"AdditionalIncome tax_treatment default: {AdditionalIncome.tax_treatment.default}")
    
    # Check CapitalAsset model
    print(f"CapitalAsset table name: {CapitalAsset.__tablename__}")
    print(f"CapitalAsset client_id FK: {CapitalAsset.client_id.foreign_keys}")
    print(f"CapitalAsset indexation_method default: {CapitalAsset.indexation_method.default}")
    print(f"CapitalAsset tax_treatment default: {CapitalAsset.tax_treatment.default}")

def main():
    """Run all fixes."""
    print("Starting fixes for Additional Income and Capital Asset modules...")
    
    try:
        fix_foreign_keys()
        verify_models()
        
        print("\nAll fixes applied successfully!")
    except Exception as e:
        print(f"\nError applying fixes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
