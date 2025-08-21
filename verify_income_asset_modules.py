"""
Verification script for Additional Income and Capital Asset modules.
This script runs all the verification steps specified in the requirements.
"""
import os
import sys
from datetime import date
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Create a test database
TEST_DB_PATH = os.path.join(BASE_DIR, "test_income_asset.db")
if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

# Create engine and session
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

# Import app modules
from app.database import Base
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset
from app.services.additional_income_service import AdditionalIncomeService
from app.services.capital_asset_service import CapitalAssetService
from app.calculation.income_integration import integrate_additional_incomes_with_scenario
from app.providers.tax_params import InMemoryTaxParamsProvider

def setup_database():
    """Create tables and verify schema."""
    print("\n=== Setting Up Database ===")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Verify tables were created
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [table[0] for table in tables]
        print(f"Created tables: {table_names}")
        
        # Check if required tables exist
        required_tables = ['client', 'additional_income', 'capital_assets']
        for table in required_tables:
            if table in table_names:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' does not exist")
    
    return True

def check_table_names():
    """Check table names in models."""
    print("\n=== Checking Table Names ===")
    
    client_table = Client.__tablename__
    additional_income_table = AdditionalIncome.__tablename__
    capital_asset_table = CapitalAsset.__tablename__
    
    print(f"Client table name: {client_table}")
    print(f"Additional Income table name: {additional_income_table}")
    print(f"Capital Asset table name: {capital_asset_table}")
    
    if client_table == 'client' and additional_income_table == 'additional_income' and capital_asset_table == 'capital_assets':
        print("✅ All table names are correct")
        return True
    else:
        print("❌ Table name mismatch")
        return False

def check_foreign_keys():
    """Check foreign key constraints."""
    print("\n=== Checking Foreign Keys ===")
    
    insp = inspect(engine)
    
    # Check additional_income foreign keys
    additional_income_fks = insp.get_foreign_keys('additional_income')
    print(f"Additional Income FKs: {additional_income_fks}")
    
    # Check capital_assets foreign keys
    capital_asset_fks = insp.get_foreign_keys('capital_assets')
    print(f"Capital Asset FKs: {capital_asset_fks}")
    
    # Verify foreign keys point to client.id
    ai_fk_valid = any(fk['referred_table'] == 'client' for fk in additional_income_fks)
    ca_fk_valid = any(fk['referred_table'] == 'client' for fk in capital_asset_fks)
    
    if ai_fk_valid:
        print("✅ Additional Income FK points to client table")
    else:
        print("❌ Additional Income FK does not point to client table")
    
    if ca_fk_valid:
        print("✅ Capital Asset FK points to client table")
    else:
        print("❌ Capital Asset FK does not point to client table")
    
    return ai_fk_valid and ca_fk_valid

def test_service_functionality():
    """Test basic service functionality."""
    print("\n=== Testing Service Functionality ===")
    
    # Create a session
    db = SessionLocal()
    
    try:
        # Create a test client
        test_client = Client(
            id_number_raw="123456789",
            id_number="123456789",
            full_name="Test Client",
            birth_date=date(1990, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.flush()  # Use flush instead of commit to get the ID while keeping the transaction open
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Create additional income
        income = AdditionalIncome(
            client_id=client_id,
            source_type="rental",
            amount=5000,
            frequency="monthly",
            start_date=date(2025, 1, 1),
            indexation_method="none",
            tax_treatment="taxable"
        )
        db.add(income)
        
        # Create capital asset
        asset = CapitalAsset(
            client_id=client_id,
            asset_type="stocks",
            current_value=100000,
            annual_return_rate=0.05,
            payment_frequency="monthly",
            start_date=date(2025, 1, 1),
            indexation_method="none",
            tax_treatment="taxable"
        )
        db.add(asset)
        
        db.commit()
        print("✅ Created test data successfully")
        
        # Test additional income service
        income_service = AdditionalIncomeService(InMemoryTaxParamsProvider())
        income_cashflow = income_service.generate_combined_cashflow(
            db, client_id, date(2025, 1, 1), date(2025, 12, 31), date(2025, 1, 1)
        )
        print(f"Generated {len(income_cashflow)} income cashflow items")
        
        # Test capital asset service
        asset_service = CapitalAssetService(InMemoryTaxParamsProvider())
        asset_cashflow = asset_service.generate_combined_cashflow(
            db, client_id, date(2025, 1, 1), date(2025, 12, 31), date(2025, 1, 1)
        )
        print(f"Generated {len(asset_cashflow)} asset cashflow items")
        
        # Test integration
        scenario_cashflow = [
            {"date": date(2025, 1, 1), "inflow": 10000, "outflow": 8000, "net": 2000}
        ]
        
        integrated_cashflow = integrate_additional_incomes_with_scenario(
            db, client_id, scenario_cashflow, date(2025, 1, 1)
        )
        print(f"Generated {len(integrated_cashflow)} integrated cashflow items")
        
        # Verify integration results
        if len(integrated_cashflow) > 0:
            item = integrated_cashflow[0]
            if item["additional_income_net"] > 0 and item["inflow"] > 10000:
                print("✅ Integration added income to cashflow correctly")
            else:
                print("❌ Integration failed to add income to cashflow")
        
        return True
    except Exception as e:
        print(f"❌ Error in service test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_api_client():
    """Test API client creation with id_number instead of id_number_raw."""
    print("\n=== Testing API Client Creation ===")
    
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Create client with id_number (not id_number_raw)
    response = client.post("/api/v1/clients", json={
        "first_name": "Test",
        "last_name": "User",
        "id_number": "123456789",
        "birth_date": "1980-01-01"
    })
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code in (200, 201):
        print("✅ Client created successfully with id_number")
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
        
        print(f"Income creation status: {income_response.status_code}")
        
        if income_response.status_code in (200, 201):
            print("✅ Additional income created successfully")
            
            # Test integration endpoint
            integration_response = client.post(f"/api/v1/clients/{client_id}/cashflow/integrate-incomes", json={
                "cashflow": [{"date": "2025-01-01", "inflow": 10000, "outflow": 8000, "net": 2000}],
                "reference_date": "2025-01-01"
            })
            
            print(f"Integration status: {integration_response.status_code}")
            
            if integration_response.status_code == 200:
                print("✅ Integration endpoint works correctly")
                data = integration_response.json()
                
                # Check if income was added to cashflow
                if any(abs(row["net"] - 7000) < 1e-6 for row in data) or any(row["inflow"] > 10000 for row in data):
                    print("✅ Integration added income to cashflow correctly")
                    return True
                else:
                    print("❌ Integration failed to add income to cashflow")
                    return False
            else:
                print(f"❌ Integration endpoint failed: {integration_response.text}")
                return False
        else:
            print(f"❌ Additional income creation failed: {income_response.text}")
            return False
    else:
        print(f"❌ Client creation failed: {response.text}")
        return False

def main():
    """Run all verification steps."""
    print("Starting verification of Additional Income and Capital Asset modules...")
    
    steps = [
        ("Database Setup", setup_database),
        ("Table Names Check", check_table_names),
        ("Foreign Keys Check", check_foreign_keys),
        ("Service Functionality", test_service_functionality),
        ("API Client Test", test_api_client)
    ]
    
    results = []
    
    for name, func in steps:
        print(f"\n{'=' * 50}")
        print(f"Running: {name}")
        print(f"{'=' * 50}")
        
        try:
            result = func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Print summary
    print("\n\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n✅ ALL VERIFICATION STEPS PASSED")
        return 0
    else:
        print("\n❌ SOME VERIFICATION STEPS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
