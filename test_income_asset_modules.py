"""
Focused test script to verify fixes for Additional Income and Capital Asset modules.
This script directly tests the models, database schema, and API endpoints.
"""
import os
import sys
import sqlite3
from datetime import date
from fastapi.testclient import TestClient

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Import app modules
from app.main import app
from app.database import engine, SessionLocal
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset

# Create test client
client = TestClient(app)

def test_model_configuration():
    """Test model configuration."""
    print("\n=== Testing Model Configuration ===")
    
    # Check table names
    print(f"Client table name: {Client.__tablename__}")
    print(f"AdditionalIncome table name: {AdditionalIncome.__tablename__}")
    print(f"CapitalAsset table name: {CapitalAsset.__tablename__}")
    
    # Check foreign keys
    print(f"AdditionalIncome client_id FK: {AdditionalIncome.client_id.foreign_keys}")
    print(f"CapitalAsset client_id FK: {CapitalAsset.client_id.foreign_keys}")
    
    # Check defaults
    print(f"AdditionalIncome indexation_method default: {AdditionalIncome.indexation_method.default}")
    print(f"AdditionalIncome indexation_method server_default: {AdditionalIncome.indexation_method.server_default}")
    print(f"AdditionalIncome tax_treatment default: {AdditionalIncome.tax_treatment.default}")
    print(f"AdditionalIncome tax_treatment server_default: {AdditionalIncome.tax_treatment.server_default}")
    
    print(f"CapitalAsset indexation_method default: {CapitalAsset.indexation_method.default}")
    print(f"CapitalAsset indexation_method server_default: {CapitalAsset.indexation_method.server_default}")
    print(f"CapitalAsset tax_treatment default: {CapitalAsset.tax_treatment.default}")
    print(f"CapitalAsset tax_treatment server_default: {CapitalAsset.tax_treatment.server_default}")
    
    # Verify foreign keys point to client.id
    ai_fk_valid = any("client.id" in str(fk) for fk in AdditionalIncome.client_id.foreign_keys)
    ca_fk_valid = any("client.id" in str(fk) for fk in CapitalAsset.client_id.foreign_keys)
    
    # Verify server defaults are set
    ai_defaults_valid = (
        AdditionalIncome.indexation_method.server_default is not None and
        AdditionalIncome.tax_treatment.server_default is not None
    )
    ca_defaults_valid = (
        CapitalAsset.indexation_method.server_default is not None and
        CapitalAsset.tax_treatment.server_default is not None
    )
    
    if ai_fk_valid and ca_fk_valid and ai_defaults_valid and ca_defaults_valid:
        print("✅ Model configuration is correct")
        return True
    else:
        print("❌ Model configuration has issues")
        return False

def test_database_schema():
    """Test database schema."""
    print("\n=== Testing Database Schema ===")
    
    # Connect to the database
    conn = sqlite3.connect('test_db.sqlite')
    cursor = conn.cursor()
    
    try:
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables in database: {tables}")
        
        # Check additional_income table schema
        if 'additional_income' in tables:
            cursor.execute("PRAGMA table_info(additional_income)")
            columns = {row[1]: row for row in cursor.fetchall()}
            print(f"Additional Income columns: {list(columns.keys())}")
            
            # Check foreign keys
            cursor.execute("PRAGMA foreign_key_list(additional_income)")
            fks = cursor.fetchall()
            print(f"Additional Income foreign keys: {fks}")
            
            # Verify foreign key points to client.id
            ai_fk_valid = any(fk[2] == 'client' and fk[3] == 'id' for fk in fks)
            
            # Verify default values
            ai_defaults_valid = (
                'indexation_method' in columns and
                'tax_treatment' in columns and
                columns['indexation_method'][4] == 'none' and
                columns['tax_treatment'][4] == 'taxable'
            )
            
            if ai_fk_valid:
                print("✅ Additional Income foreign key is correct")
            else:
                print("❌ Additional Income foreign key is incorrect")
            
            if ai_defaults_valid:
                print("✅ Additional Income default values are correct")
            else:
                print("❌ Additional Income default values are incorrect")
        else:
            print("❌ Additional Income table does not exist")
            ai_fk_valid = ai_defaults_valid = False
        
        # Check capital_assets table schema
        if 'capital_assets' in tables:
            cursor.execute("PRAGMA table_info(capital_assets)")
            columns = {row[1]: row for row in cursor.fetchall()}
            print(f"Capital Assets columns: {list(columns.keys())}")
            
            # Check foreign keys
            cursor.execute("PRAGMA foreign_key_list(capital_assets)")
            fks = cursor.fetchall()
            print(f"Capital Assets foreign keys: {fks}")
            
            # Verify foreign key points to client.id
            ca_fk_valid = any(fk[2] == 'client' and fk[3] == 'id' for fk in fks)
            
            # Verify default values
            ca_defaults_valid = (
                'indexation_method' in columns and
                'tax_treatment' in columns and
                columns['indexation_method'][4] == 'none' and
                columns['tax_treatment'][4] == 'taxable'
            )
            
            if ca_fk_valid:
                print("✅ Capital Assets foreign key is correct")
            else:
                print("❌ Capital Assets foreign key is incorrect")
            
            if ca_defaults_valid:
                print("✅ Capital Assets default values are correct")
            else:
                print("❌ Capital Assets default values are incorrect")
        else:
            print("❌ Capital Assets table does not exist")
            ca_fk_valid = ca_defaults_valid = False
        
        if ai_fk_valid and ca_fk_valid and ai_defaults_valid and ca_defaults_valid:
            print("✅ Database schema is correct")
            return True
        else:
            print("❌ Database schema has issues")
            return False
    finally:
        conn.close()

def test_client_api():
    """Test client API with id_number instead of id_number_raw."""
    print("\n=== Testing Client API ===")
    
    # Create client with id_number (not id_number_raw)
    response = client.post("/api/v1/clients", json={
        "first_name": "Test",
        "last_name": "User",
        "id_number": "123456789",
        "birth_date": "1980-01-01"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code in (200, 201):
        print("✅ Client API accepts id_number")
        return True, response.json()["id"]
    else:
        print("❌ Client API does not accept id_number")
        return False, None

def test_additional_income_api(client_id):
    """Test additional income API."""
    print("\n=== Testing Additional Income API ===")
    
    # Create additional income
    response = client.post(f"/api/v1/clients/{client_id}/additional-incomes", json={
        "source_type": "rental",
        "amount": 5000,
        "frequency": "monthly",
        "start_date": "2025-01-01",
        "indexation_method": "none",
        "tax_treatment": "taxable"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code in (200, 201):
        print("✅ Additional Income API works")
        return True, response.json()["id"]
    else:
        print("❌ Additional Income API does not work")
        return False, None

def test_capital_asset_api(client_id):
    """Test capital asset API."""
    print("\n=== Testing Capital Asset API ===")
    
    # Create capital asset
    response = client.post(f"/api/v1/clients/{client_id}/capital-assets", json={
        "asset_type": "stocks",
        "current_value": 100000,
        "annual_return_rate": 0.05,
        "payment_frequency": "monthly",
        "start_date": "2025-01-01",
        "indexation_method": "none",
        "tax_treatment": "taxable"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code in (200, 201):
        print("✅ Capital Asset API works")
        return True, response.json()["id"]
    else:
        print("❌ Capital Asset API does not work")
        return False, None

def test_integration_api(client_id):
    """Test integration API."""
    print("\n=== Testing Integration API ===")
    
    # Test income integration
    response = client.post(f"/api/v1/clients/{client_id}/cashflow/integrate-incomes", json={
        "cashflow": [{"date": "2025-01-01", "inflow": 10000, "outflow": 8000, "net": 2000}],
        "reference_date": "2025-01-01"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code == 200:
        print("✅ Income Integration API works")
        income_integration_ok = True
    else:
        print("❌ Income Integration API does not work")
        income_integration_ok = False
    
    # Test asset integration
    response = client.post(f"/api/v1/clients/{client_id}/cashflow/integrate-assets", json={
        "cashflow": [{"date": "2025-01-01", "inflow": 10000, "outflow": 8000, "net": 2000}],
        "reference_date": "2025-01-01"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code == 200:
        print("✅ Asset Integration API works")
        asset_integration_ok = True
    else:
        print("❌ Asset Integration API does not work")
        asset_integration_ok = False
    
    # Test combined integration
    response = client.post(f"/api/v1/clients/{client_id}/cashflow/integrate-all", json={
        "cashflow": [{"date": "2025-01-01", "inflow": 10000, "outflow": 8000, "net": 2000}],
        "reference_date": "2025-01-01"
    })
    
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json() if response.status_code < 400 else response.text}")
    
    if response.status_code == 200:
        print("✅ Combined Integration API works")
        combined_integration_ok = True
    else:
        print("❌ Combined Integration API does not work")
        combined_integration_ok = False
    
    return income_integration_ok and asset_integration_ok and combined_integration_ok

def main():
    """Run all tests."""
    print("Starting tests for Additional Income and Capital Asset modules...")
    
    # Test model configuration
    model_ok = test_model_configuration()
    
    # Test database schema
    schema_ok = test_database_schema()
    
    # Test client API
    client_ok, client_id = test_client_api()
    
    if client_ok and client_id:
        # Test additional income API
        income_ok, _ = test_additional_income_api(client_id)
        
        # Test capital asset API
        asset_ok, _ = test_capital_asset_api(client_id)
        
        # Test integration API
        integration_ok = test_integration_api(client_id)
    else:
        income_ok = asset_ok = integration_ok = False
    
    # Print summary
    print("\n\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    print(f"Model Configuration: {'✅ PASSED' if model_ok else '❌ FAILED'}")
    print(f"Database Schema: {'✅ PASSED' if schema_ok else '❌ FAILED'}")
    print(f"Client API: {'✅ PASSED' if client_ok else '❌ FAILED'}")
    print(f"Additional Income API: {'✅ PASSED' if income_ok else '❌ FAILED'}")
    print(f"Capital Asset API: {'✅ PASSED' if asset_ok else '❌ FAILED'}")
    print(f"Integration API: {'✅ PASSED' if integration_ok else '❌ FAILED'}")
    
    all_passed = model_ok and schema_ok and client_ok and income_ok and asset_ok and integration_ok
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
