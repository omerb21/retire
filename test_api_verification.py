import os
import sys
import time
import webbrowser
import requests
import json
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_CLIENT_ID = 1  # Change this to a valid client ID in your system

# Test data
test_pension_fund = {
    "client_id": TEST_CLIENT_ID,
    "fund_name": "Test Pension Fund",
    "input_mode": "calculated",
    "balance": 500000,
    "annuity_factor": 220,
    "pension_start_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
    "indexation_method": "fixed",
    "fixed_index_rate": 0.02
}

test_additional_income = {
    "client_id": TEST_CLIENT_ID,
    "name": "Test Additional Income",
    "amount": 5000,
    "frequency": "monthly",
    "start_date": datetime.now().strftime("%Y-%m-%d"),
    "end_date": (datetime.now() + timedelta(days=365*5)).strftime("%Y-%m-%d"),
    "indexation_method": "fixed",
    "fixed_index_rate": 0.02,
    "tax_treatment": "taxable"
}

test_capital_asset = {
    "client_id": TEST_CLIENT_ID,
    "name": "Test Capital Asset",
    "amount": 1000000,
    "return_rate": 0.04,
    "payment_frequency": "monthly",
    "start_date": datetime.now().strftime("%Y-%m-%d"),
    "end_date": (datetime.now() + timedelta(days=365*10)).strftime("%Y-%m-%d"),
    "indexation_method": "cpi",
    "tax_treatment": "taxable"
}

test_scenario = {
    "client_id": TEST_CLIENT_ID,
    "scenario_name": "Test Scenario",
    "monthly_expenses": 10000,
    "tax_optimization": True,
    "capitalization": False
}

# Helper functions
def api_request(endpoint, method="GET", data=None):
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=json.dumps(data) if data else None)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            print(f"Unsupported method: {method}")
            return None
        
        if response.status_code >= 400:
            print(f"Error {response.status_code}: {response.text}")
            return None
        
        return response.json() if response.text else {"status": "success"}
    except Exception as e:
        print(f"API request failed: {e}")
        return None

def run_api_tests():
    print("\n=== Running API Tests ===\n")
    
    # Test 1: Create a pension fund
    print("Test 1: Creating pension fund...")
    pension_fund = api_request(f"/clients/{TEST_CLIENT_ID}/pension-funds", "POST", test_pension_fund)
    if pension_fund:
        print(f"✓ Pension fund created with ID: {pension_fund.get('id')}")
        pension_fund_id = pension_fund.get('id')
    else:
        print("✗ Failed to create pension fund")
        pension_fund_id = None
    
    # Test 2: List pension funds
    print("\nTest 2: Listing pension funds...")
    funds = api_request(f"/clients/{TEST_CLIENT_ID}/pension-funds")
    if funds and isinstance(funds, list):
        print(f"✓ Found {len(funds)} pension funds")
    else:
        print("✗ Failed to list pension funds")
    
    # Test 3: Create additional income
    print("\nTest 3: Creating additional income...")
    income = api_request(f"/clients/{TEST_CLIENT_ID}/additional-incomes", "POST", test_additional_income)
    if income:
        print(f"✓ Additional income created with ID: {income.get('id')}")
        income_id = income.get('id')
    else:
        print("✗ Failed to create additional income")
        income_id = None
    
    # Test 4: Create capital asset
    print("\nTest 4: Creating capital asset...")
    asset = api_request(f"/clients/{TEST_CLIENT_ID}/capital-assets", "POST", test_capital_asset)
    if asset:
        print(f"✓ Capital asset created with ID: {asset.get('id')}")
        asset_id = asset.get('id')
    else:
        print("✗ Failed to create capital asset")
        asset_id = None
    
    # Test 5: Create scenario
    print("\nTest 5: Creating scenario...")
    scenario = api_request(f"/clients/{TEST_CLIENT_ID}/scenarios", "POST", test_scenario)
    if scenario:
        print(f"✓ Scenario created with ID: {scenario.get('id')}")
        scenario_id = scenario.get('id')
    else:
        print("✗ Failed to create scenario")
        scenario_id = None
    
    # Test 6: Integrate scenario
    if scenario_id:
        print("\nTest 6: Integrating scenario...")
        integration = api_request(f"/clients/{TEST_CLIENT_ID}/scenarios/{scenario_id}/integrate", "POST")
        if integration:
            print("✓ Scenario integration successful")
        else:
            print("✗ Failed to integrate scenario")
    
    # Test 7: Compute fixation
    print("\nTest 7: Computing fixation...")
    fixation = api_request(f"/fixation/{TEST_CLIENT_ID}/compute", "POST")
    if fixation:
        print("✓ Fixation computation successful")
    else:
        print("✗ Failed to compute fixation")
    
    # Cleanup: Delete created resources
    print("\n=== Cleanup ===\n")
    
    if pension_fund_id:
        print(f"Deleting pension fund {pension_fund_id}...")
        result = api_request(f"/clients/{TEST_CLIENT_ID}/pension-funds/{pension_fund_id}", "DELETE")
        print("✓ Deleted" if result else "✗ Failed to delete")
    
    if income_id:
        print(f"Deleting additional income {income_id}...")
        result = api_request(f"/clients/{TEST_CLIENT_ID}/additional-incomes/{income_id}", "DELETE")
        print("✓ Deleted" if result else "✗ Failed to delete")
    
    if asset_id:
        print(f"Deleting capital asset {asset_id}...")
        result = api_request(f"/clients/{TEST_CLIENT_ID}/capital-assets/{asset_id}", "DELETE")
        print("✓ Deleted" if result else "✗ Failed to delete")

# Main execution
def main():
    # Get the absolute path to the API verification HTML file
    api_verification_path = Path(__file__).parent / "api_verification.html"

    # Check if the file exists
    if not api_verification_path.exists():
        print(f"Error: {api_verification_path} not found")
        sys.exit(1)

    # Convert to absolute file URL
    file_url = f"file:///{api_verification_path.absolute().as_posix()}"

    # Open the file in the default web browser
    print(f"Opening {file_url}")
    webbrowser.open(file_url)

    print("\nAPI verification page opened in browser.")
    print("Please test the following functionality:")
    print("1. Pension fund creation and deletion (both calculated and manual modes)")
    print("2. Fixation computation")
    print("3. Scenario creation and listing")
    print("4. Additional income and capital asset management")
    print("5. Integration with scenarios")
    
    # Ask if user wants to run automated API tests
    choice = input("\nWould you like to run automated API tests? (y/n): ")
    if choice.lower() == 'y':
        run_api_tests()

if __name__ == "__main__":
    main()
