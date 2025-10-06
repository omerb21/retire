"""
Manual test script for pension fund calculation features
"""
import sys
import json
import traceback
from datetime import date, datetime
from fastapi.testclient import TestClient

try:
    from app.main import app
    from app.database import get_db, SessionLocal
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
except Exception as e:
    print(f"Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Create test client
client = TestClient(app)

# Override database dependency
def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def setup_test_data():
    """Set up test data for pension fund calculations"""
    db = next(override_get_db())
    
    # Check if test client exists
    test_client = db.query(Client).filter(Client.id_number == "999999999").first()
    if not test_client:
        # Create test client
        test_client = Client(
            first_name="Test",
            last_name="User",
            id_number="999999999",
            birth_date=date(1970, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        print(f"Created test client with ID: {test_client.id}")
    else:
        print(f"Using existing test client with ID: {test_client.id}")
    
    # Check if test pension funds exist
    funds = db.query(PensionFund).filter(PensionFund.client_id == test_client.id).all()
    if not funds:
        # Create test pension funds
        funds = [
            PensionFund(
                client_id=test_client.id,
                fund_name="קרן פנסיה מקיפה",
                fund_type="פנסיה",
                input_mode="calculated",
                balance=1000000.0,
                annuity_factor=200.0,
                pension_start_date=date(2023, 1, 1),
                indexation_method="none",
                remarks="קרן פנסיה לבדיקה"
            ),
            PensionFund(
                client_id=test_client.id,
                fund_name="קופת גמל",
                fund_type="גמל",
                input_mode="manual",
                pension_amount=3000.0,
                pension_start_date=date(2023, 1, 1),
                indexation_method="fixed",
                fixed_index_rate=0.02,
                remarks="קופת גמל לבדיקה"
            ),
            PensionFund(
                client_id=test_client.id,
                fund_name="ביטוח מנהלים",
                fund_type="ביטוח",
                input_mode="calculated",
                balance=500000.0,
                annuity_factor=180.0,
                pension_start_date=date(2023, 6, 1),
                indexation_method="cpi",
                remarks="ביטוח מנהלים לבדיקה"
            )
        ]
        for fund in funds:
            db.add(fund)
        db.commit()
        print(f"Created {len(funds)} test pension funds")
    else:
        print(f"Using {len(funds)} existing pension funds")
    
    return test_client.id

def test_get_pension_funds(client_id):
    """Test getting pension funds for a client"""
    response = client.get(f"/api/v1/clients/{client_id}/pension-funds")
    print("\n=== GET PENSION FUNDS ===")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        funds = response.json()
        print(f"Found {len(funds)} pension funds:")
        for fund in funds:
            print(f"- {fund['fund_name']} ({fund['fund_type']}): {fund.get('pension_amount', 'Not calculated')}")
        return funds
    else:
        print(f"Error: {response.text}")
        return []

def test_compute_pension_fund(fund_id):
    """Test computing a pension fund"""
    response = client.post(f"/api/v1/pension-funds/{fund_id}/compute")
    print(f"\n=== COMPUTE PENSION FUND {fund_id} ===")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        fund = response.json()
        print(f"Fund: {fund['fund_name']}")
        print(f"Pension amount: {fund['pension_amount']}")
        print(f"Indexed pension amount: {fund['indexed_pension_amount']}")
        return fund
    else:
        print(f"Error: {response.text}")
        return None

def test_compute_all_pension_funds(client_id):
    """Test computing all pension funds for a client"""
    response = client.post(f"/api/v1/clients/{client_id}/pension-funds/compute-all")
    print(f"\n=== COMPUTE ALL PENSION FUNDS ===")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        funds = response.json()
        print(f"Computed {len(funds)} pension funds:")
        for fund in funds:
            print(f"- {fund['fund_name']}: {fund['pension_amount']} → {fund['indexed_pension_amount']}")
        return funds
    else:
        print(f"Error: {response.text}")
        return []

def test_pension_cashflow(client_id):
    """Test getting pension cashflow for a client"""
    response = client.post(
        f"/api/v1/clients/{client_id}/pension-cashflow",
        params={"months": 6}
    )
    print(f"\n=== PENSION CASHFLOW ===")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        cashflow = response.json()
        print(f"Generated cashflow for {len(cashflow)} months:")
        for cf in cashflow:
            print(f"- {cf['date']}: {cf['total_amount']} ({len(cf['funds'])} funds)")
        return cashflow
    else:
        print(f"Error: {response.text}")
        return []

def test_pension_scenario(client_id):
    """Test pension scenario calculation"""
    scenario_data = {
        "scenario": {
            "planned_termination_date": (date.today()).isoformat(),
            "other_incomes_monthly": 5000,
            "monthly_expenses": 7000
        },
        "include_pension_funds": True
    }
    
    response = client.post(
        f"/api/v1/clients/{client_id}/pension-scenario",
        json=scenario_data
    )
    print(f"\n=== PENSION SCENARIO ===")
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Scenario results:")
        print(f"- Pension monthly: {result.get('pension_monthly', 'N/A')}")
        print(f"- Grant net: {result.get('grant_net', 'N/A')}")
        print(f"- Cashflow months: {len(result.get('cashflow', []))}")
        
        # Print first month cashflow details
        if result.get('cashflow'):
            first_month = result['cashflow'][0]
            print(f"\nFirst month cashflow:")
            print(f"- Date: {first_month.get('date')}")
            print(f"- Inflow: {first_month.get('inflow')}")
            print(f"- Outflow: {first_month.get('outflow')}")
            print(f"- Net: {first_month.get('net')}")
            print(f"- Pension income: {first_month.get('pension_income')}")
            
            if first_month.get('pension_funds'):
                print(f"- Pension funds: {len(first_month['pension_funds'])}")
                for fund in first_month['pension_funds']:
                    print(f"  * {fund['fund_name']}: {fund['amount']}")
        
        return result
    else:
        print(f"Error: {response.text}")
        return None

def main():
    """Main function to run all tests"""
    print("=== PENSION FUND CALCULATION TEST ===")
    
    try:
        # Setup test data
        client_id = setup_test_data()
        
        # Run tests
        funds = test_get_pension_funds(client_id)
        
        if funds:
            # Test computing individual funds
            for fund in funds:
                test_compute_pension_fund(fund['id'])
            
            # Test computing all funds
            test_compute_all_pension_funds(client_id)
            
            # Test pension cashflow
            test_pension_cashflow(client_id)
            
            # Test pension scenario
            test_pension_scenario(client_id)
        
        print("\n=== TEST COMPLETED ===")
    except Exception as e:
        print(f"\n=== TEST FAILED: {e} ===")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
