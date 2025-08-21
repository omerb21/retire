"""
API Smoke Test for Additional Income and Capital Asset endpoints.
This script tests the basic functionality of the API endpoints.
"""

import requests
import json
from datetime import date, datetime
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def print_response(response, message=""):
    """Print response in a formatted way"""
    print(f"\n{message}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2, default=json_serial)}")
    except:
        print(f"Response: {response.text}")

def create_test_client():
    """Create a test client"""
    client_data = {
        "id_number_raw": "123456789",
        "full_name": "Test Client",
        "birth_date": "1980-01-01"
    }
    
    response = requests.post(f"{BASE_URL}/clients/", json=client_data)
    print_response(response, "Creating test client")
    
    if response.status_code == 201:
        return response.json()["id"]
    else:
        print("Failed to create test client")
        sys.exit(1)

def test_additional_income(client_id):
    """Test additional income endpoints"""
    print("\n=== Testing Additional Income Endpoints ===")
    
    # Create additional income
    income_data = {
        "name": "Rental Income",
        "income_type": "rental",
        "amount": 5000,
        "frequency": "monthly",
        "start_date": "2023-01-01",
        "end_date": "2030-12-31",
        "indexation_method": "cpi",
        "indexation_rate": None,
        "tax_treatment": "taxable",
        "tax_rate": None
    }
    
    response = requests.post(
        f"{BASE_URL}/clients/{client_id}/additional-incomes/", 
        json=income_data
    )
    print_response(response, "Creating additional income")
    
    if response.status_code != 201:
        print("Failed to create additional income")
        return
    
    income_id = response.json()["id"]
    
    # Get all additional incomes
    response = requests.get(f"{BASE_URL}/clients/{client_id}/additional-incomes/")
    print_response(response, "Getting all additional incomes")
    
    # Get specific additional income
    response = requests.get(f"{BASE_URL}/clients/{client_id}/additional-incomes/{income_id}")
    print_response(response, "Getting specific additional income")
    
    # Update additional income
    update_data = {
        "amount": 5500,
        "indexation_method": "fixed",
        "indexation_rate": 2.0
    }
    
    response = requests.put(
        f"{BASE_URL}/clients/{client_id}/additional-incomes/{income_id}", 
        json=update_data
    )
    print_response(response, "Updating additional income")
    
    # Delete additional income
    response = requests.delete(f"{BASE_URL}/clients/{client_id}/additional-incomes/{income_id}")
    print_response(response, "Deleting additional income")
    
    return income_id

def test_capital_asset(client_id):
    """Test capital asset endpoints"""
    print("\n=== Testing Capital Asset Endpoints ===")
    
    # Create capital asset
    asset_data = {
        "name": "Investment Property",
        "asset_type": "real_estate",
        "initial_value": 1000000,
        "current_value": 1200000,
        "acquisition_date": "2015-01-01",
        "return_rate": 4.5,
        "payment_frequency": "monthly",
        "indexation_method": "fixed",
        "indexation_rate": 2.0,
        "tax_treatment": "taxable",
        "tax_rate": 25.0
    }
    
    response = requests.post(
        f"{BASE_URL}/clients/{client_id}/capital-assets/", 
        json=asset_data
    )
    print_response(response, "Creating capital asset")
    
    if response.status_code != 201:
        print("Failed to create capital asset")
        return
    
    asset_id = response.json()["id"]
    
    # Get all capital assets
    response = requests.get(f"{BASE_URL}/clients/{client_id}/capital-assets/")
    print_response(response, "Getting all capital assets")
    
    # Get specific capital asset
    response = requests.get(f"{BASE_URL}/clients/{client_id}/capital-assets/{asset_id}")
    print_response(response, "Getting specific capital asset")
    
    # Update capital asset
    update_data = {
        "current_value": 1250000,
        "return_rate": 5.0
    }
    
    response = requests.put(
        f"{BASE_URL}/clients/{client_id}/capital-assets/{asset_id}", 
        json=update_data
    )
    print_response(response, "Updating capital asset")
    
    # Delete capital asset
    response = requests.delete(f"{BASE_URL}/clients/{client_id}/capital-assets/{asset_id}")
    print_response(response, "Deleting capital asset")
    
    return asset_id

def test_integration(client_id, income_id, asset_id):
    """Test integration endpoints"""
    print("\n=== Testing Integration Endpoints ===")
    
    # Create test cashflow
    cashflow = [
        {
            "date": "2023-01-01",
            "inflow": 10000,
            "outflow": 8000,
            "net": 2000
        },
        {
            "date": "2023-02-01",
            "inflow": 10000,
            "outflow": 8000,
            "net": 2000
        },
        {
            "date": "2023-03-01",
            "inflow": 10000,
            "outflow": 8000,
            "net": 2000
        }
    ]
    
    # Test integrate-incomes endpoint
    response = requests.post(
        f"{BASE_URL}/clients/{client_id}/cashflow/integrate-incomes",
        json=cashflow
    )
    print_response(response, "Testing integrate-incomes endpoint")
    
    # Test integrate-assets endpoint
    response = requests.post(
        f"{BASE_URL}/clients/{client_id}/cashflow/integrate-assets",
        json=cashflow
    )
    print_response(response, "Testing integrate-assets endpoint")
    
    # Test integrate-all endpoint
    response = requests.post(
        f"{BASE_URL}/clients/{client_id}/cashflow/integrate-all",
        json=cashflow
    )
    print_response(response, "Testing integrate-all endpoint")

def main():
    """Main function to run the smoke test"""
    print("Starting API Smoke Test...")
    
    # Create test client
    client_id = create_test_client()
    print(f"Created test client with ID: {client_id}")
    
    # Test additional income endpoints
    income_id = test_additional_income(client_id)
    
    # Test capital asset endpoints
    asset_id = test_capital_asset(client_id)
    
    # Test integration endpoints
    test_integration(client_id, income_id, asset_id)
    
    print("\nAPI Smoke Test completed!")

if __name__ == "__main__":
    main()
