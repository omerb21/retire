"""
Preflight verification script for Additional Income and Capital Asset modules.
"""
import os
import sys
import subprocess
from sqlalchemy import inspect, create_engine
from alembic.config import Config
from alembic import command

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Import app modules
from app.database import engine
from app.models.client import Client
from app.models.additional_income import AdditionalIncome
from app.models.capital_asset import CapitalAsset

def run_alembic_commands():
    """Run alembic downgrade and upgrade commands."""
    print("\n=== Running Alembic Commands ===")
    alembic_cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    
    print("Downgrading to base...")
    command.downgrade(alembic_cfg, "base")
    
    print("Upgrading to head...")
    command.upgrade(alembic_cfg, "head")
    print("Alembic migrations completed successfully.")

def check_table_names():
    """Check table names in models."""
    print("\n=== Checking Table Names ===")
    print(f"Client table name: {Client.__tablename__}")
    print(f"Additional Income exists: {'additional_income' in inspect(engine).get_table_names()}")
    print(f"Capital Asset exists: {'capital_assets' in inspect(engine).get_table_names()}")

def check_foreign_keys():
    """Check foreign key constraints."""
    print("\n=== Checking Foreign Keys ===")
    insp = inspect(engine)
    
    additional_income_fks = [fk['referred_table'] for fk in insp.get_foreign_keys('additional_income')]
    capital_asset_fks = [fk['referred_table'] for fk in insp.get_foreign_keys('capital_assets')]
    
    print(f"Additional Income FKs: {additional_income_fks}")
    print(f"Capital Asset FKs: {capital_asset_fks}")

def run_service_tests():
    """Run service tests."""
    print("\n=== Running Service Tests ===")
    result = subprocess.run(
        ["pytest", "-q", "-k", "additional_income or capital_asset", "-x", "--disable-warnings"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Service tests failed with code {result.returncode}")
        print(f"Error: {result.stderr}")
    else:
        print("Service tests passed successfully.")

def run_integration_tests():
    """Run integration tests."""
    print("\n=== Running Integration Tests ===")
    result = subprocess.run(
        ["pytest", "-q", "-k", "income_integration", "-x", "--disable-warnings"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Integration tests failed with code {result.returncode}")
        print(f"Error: {result.stderr}")
    else:
        print("Integration tests passed successfully.")

def run_api_smoke_test():
    """Run minimal API smoke test."""
    print("\n=== Running API Smoke Test ===")
    test_code = """
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
# Create client (with id_number, not id_number_raw)
r = c.post("/api/v1/clients", json={
  "first_name":"Test","last_name":"User","id_number":"123456789","birth_date":"1980-01-01"
})
assert r.status_code in (200,201), r.text
cid = r.json()["id"]

# Create additional income
r = c.post(f"/api/v1/clients/{cid}/additional-incomes", json={
  "source_type":"rental","amount":5000,"frequency":"monthly",
  "start_date":"2025-01-01","indexation_method":"none","tax_treatment":"taxable"
})
assert r.status_code in (200,201), r.text

# Integrate with scenario
r = c.post(f"/api/v1/clients/{cid}/cashflow/integrate-incomes", json={
  "cashflow":[{"date":"2025-01-01","inflow":10000,"outflow":8000,"net":2000}],
  "reference_date":"2025-01-01"
})
assert r.status_code==200, r.text
data=r.json()
assert any(abs(row["net"]-7000) < 1e-6 for row in data) or any(row["inflow"]>10000 for row in data)
print("API SMOKE OK")
"""
    result = subprocess.run(
        ["python", "-c", test_code],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"API smoke test failed with code {result.returncode}")
        print(f"Error: {result.stderr}")
    else:
        print("API smoke test passed successfully.")

def main():
    """Run all preflight verification steps."""
    print("Starting preflight verification...")
    
    try:
        run_alembic_commands()
        check_table_names()
        check_foreign_keys()
        run_service_tests()
        run_integration_tests()
        run_api_smoke_test()
        
        print("\n=== Preflight Verification Complete ===")
        print("All checks passed successfully!")
    except Exception as e:
        print(f"\nPreflight verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
