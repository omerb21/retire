"""
Script to fix and verify Additional Income and Capital Asset modules.
"""
import os
import sys
from datetime import date
from sqlalchemy import create_engine, text

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Import app modules
from app.database import engine, SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset

def fix_models():
    """Fix model issues."""
    print("Fixing model issues...")
    
    # Fix AdditionalIncome model
    AdditionalIncome.__table__.constraints.clear()
    AdditionalIncome.client_id.foreign_keys.clear()
    AdditionalIncome.client_id.foreign_keys.add("client.id")
    
    # Fix CapitalAsset model
    CapitalAsset.__table__.constraints.clear()
    CapitalAsset.client_id.foreign_keys.clear()
    CapitalAsset.client_id.foreign_keys.add("client.id")
    
    print("Model fixes applied.")

def fix_database():
    """Fix database issues."""
    print("Fixing database issues...")
    
    # Create a session
    db = SessionLocal()
    try:
        # Check if tables exist
        with engine.connect() as conn:
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
            table_names = [table[0] for table in tables]
            print(f"Existing tables: {table_names}")
            
            # Fix additional_income table if it exists
            if 'additional_income' in table_names:
                try:
                    # Drop foreign key constraint
                    conn.execute(text("PRAGMA foreign_keys = OFF"))
                    conn.execute(text("""
                    CREATE TABLE additional_income_new (
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
                        FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE
                    )
                    """))
                    
                    # Copy data
                    conn.execute(text("INSERT INTO additional_income_new SELECT * FROM additional_income"))
                    
                    # Replace table
                    conn.execute(text("DROP TABLE additional_income"))
                    conn.execute(text("ALTER TABLE additional_income_new RENAME TO additional_income"))
                    
                    # Create indexes
                    conn.execute(text("CREATE INDEX ix_additional_income_id ON additional_income (id)"))
                    conn.execute(text("CREATE INDEX ix_additional_income_client_id ON additional_income (client_id)"))
                    
                    print("Fixed additional_income table.")
                except Exception as e:
                    print(f"Error fixing additional_income table: {e}")
            
            # Fix capital_assets table if it exists
            if 'capital_assets' in table_names:
                try:
                    # Drop foreign key constraint
                    conn.execute(text("PRAGMA foreign_keys = OFF"))
                    conn.execute(text("""
                    CREATE TABLE capital_assets_new (
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
                        FOREIGN KEY(client_id) REFERENCES client (id) ON DELETE CASCADE
                    )
                    """))
                    
                    # Copy data
                    conn.execute(text("INSERT INTO capital_assets_new SELECT * FROM capital_assets"))
                    
                    # Replace table
                    conn.execute(text("DROP TABLE capital_assets"))
                    conn.execute(text("ALTER TABLE capital_assets_new RENAME TO capital_assets"))
                    
                    # Create indexes
                    conn.execute(text("CREATE INDEX ix_capital_assets_id ON capital_assets (id)"))
                    conn.execute(text("CREATE INDEX ix_capital_assets_client_id ON capital_assets (client_id)"))
                    
                    print("Fixed capital_assets table.")
                except Exception as e:
                    print(f"Error fixing capital_assets table: {e}")
            
            # Re-enable foreign keys
            conn.execute(text("PRAGMA foreign_keys = ON"))
        
        db.commit()
        print("Database fixes applied.")
    except Exception as e:
        db.rollback()
        print(f"Error fixing database: {e}")
    finally:
        db.close()

def run_verification_steps():
    """Run verification steps."""
    print("\nRunning verification steps...")
    
    # Check table names
    print("\nChecking table names:")
    print(f"Client table name: {Client.__tablename__}")
    print(f"Additional Income table name: {AdditionalIncome.__tablename__}")
    print(f"Capital Asset table name: {CapitalAsset.__tablename__}")
    
    # Check foreign keys
    print("\nChecking foreign keys:")
    print(f"Additional Income client_id FK: {AdditionalIncome.client_id.foreign_keys}")
    print(f"Capital Asset client_id FK: {CapitalAsset.client_id.foreign_keys}")
    
    # Run API smoke test
    print("\nRunning API smoke test:")
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Create client with id_number (not id_number_raw)
    try:
        response = client.post("/api/v1/clients", json={
            "first_name": "Test",
            "last_name": "User",
            "id_number": "123456789",
            "birth_date": "1980-01-01"
        })
        
        print(f"Client creation response status: {response.status_code}")
        
        if response.status_code in (200, 201):
            client_data = response.json()
            client_id = client_data["id"]
            
            # Create additional income
            income_response = client.post(f"/api/v1/clients/{client_id}/additional-incomes", json={
                "source_type": "rental",
                "amount": 5000,
                "frequency": "monthly",
                "start_date": "2025-01-01",
                "indexation_method": "none",
                "tax_treatment": "taxable"
            })
            
            print(f"Income creation response status: {income_response.status_code}")
            
            if income_response.status_code in (200, 201):
                # Test integration endpoint
                integration_response = client.post(f"/api/v1/clients/{client_id}/cashflow/integrate-incomes", json={
                    "cashflow": [{"date": "2025-01-01", "inflow": 10000, "outflow": 8000, "net": 2000}],
                    "reference_date": "2025-01-01"
                })
                
                print(f"Integration response status: {integration_response.status_code}")
                
                if integration_response.status_code == 200:
                    data = integration_response.json()
                    if any(abs(row["net"] - 7000) < 1e-6 for row in data) or any(row["inflow"] > 10000 for row in data):
                        print("API SMOKE TEST PASSED")
                    else:
                        print("API SMOKE TEST FAILED: Income not added to cashflow")
                else:
                    print(f"API SMOKE TEST FAILED: Integration failed - {integration_response.text}")
            else:
                print(f"API SMOKE TEST FAILED: Income creation failed - {income_response.text}")
        else:
            print(f"API SMOKE TEST FAILED: Client creation failed - {response.text}")
    except Exception as e:
        print(f"API SMOKE TEST FAILED: {e}")

def main():
    """Run all fixes and verification steps."""
    print("Starting fixes and verification for Additional Income and Capital Asset modules...")
    
    try:
        # Fix model issues
        fix_models()
        
        # Fix database issues
        fix_database()
        
        # Run verification steps
        run_verification_steps()
        
        print("\nAll fixes and verification steps completed.")
    except Exception as e:
        print(f"\nError during fixes and verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
