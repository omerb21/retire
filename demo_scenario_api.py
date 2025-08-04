#!/usr/bin/env python3
"""
Demo script for scenario persistence API endpoints
"""
import requests
import json
from datetime import date

BASE_URL = "http://127.0.0.1:8000"

def create_demo_client():
    """Create a demo client for testing"""
    client_data = {
        "id_number_raw": "123456789",
        "full_name": "דמו לקוח",
        "birth_date": "1980-01-01",
        "email": "demo@test.com",
        "phone": "0500000000"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients", json=client_data)
    if response.status_code == 201:
        client = response.json()
        print(f"✅ Created client: {client['id']} - {client['full_name']}")
        return client['id']
    else:
        print(f"❌ Failed to create client: {response.status_code} - {response.text}")
        return None

def create_demo_employment(client_id):
    """Create demo employment for client"""
    # First create employer
    employer_data = {
        "name": "חברת הדמו",
        "reg_no": "987654321"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/employers", json=employer_data)
    if response.status_code == 201:
        employer = response.json()
        employer_id = employer['id']
        print(f"✅ Created employer: {employer_id} - {employer['name']}")
    else:
        print(f"❌ Failed to create employer: {response.status_code} - {response.text}")
        return False
    
    # Set current employment
    employment_data = {
        "employer_id": employer_id,
        "start_date": "2023-01-01"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/employment/set-current", json=employment_data)
    if response.status_code == 200:
        print(f"✅ Set current employment for client {client_id}")
        return True
    else:
        print(f"❌ Failed to set employment: {response.status_code} - {response.text}")
        return False

def test_calculation_endpoint(client_id):
    """Test basic calculation endpoint"""
    scenario_data = {
        "planned_termination_date": "2025-06-01",
        "monthly_expenses": 8000.0,
        "other_incomes_monthly": 2000.0
    }
    
    print(f"\n🧮 Testing calculation endpoint for client {client_id}")
    response = requests.post(f"{BASE_URL}/api/v1/calc/{client_id}", json=scenario_data)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Calculation successful!")
        print(f"📊 Results summary:")
        print(f"   - Seniority years: {result['seniority_years']}")
        print(f"   - Grant gross: ₪{result['grant_gross']:,.2f}")
        print(f"   - Grant net: ₪{result['grant_net']:,.2f}")
        print(f"   - Monthly pension: ₪{result['pension_monthly']:,.2f}")
        print(f"   - Cashflow points: {len(result['cashflow'])}")
        return result
    else:
        print(f"❌ Calculation failed: {response.status_code} - {response.text}")
        return None

def test_scenario_persistence(client_id):
    """Test scenario persistence endpoints"""
    print(f"\n💾 Testing scenario persistence for client {client_id}")
    
    # 1. Create scenario
    scenario_data = {
        "scenario_name": "תרחיש דמו - פרישה מוקדמת",
        "planned_termination_date": "2025-06-01",
        "monthly_expenses": 8000.0,
        "retirement_age": 62,
        "other_incomes_monthly": 2000.0
    }
    
    print("📝 Creating new scenario...")
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/scenarios", json=scenario_data)
    
    if response.status_code == 201:
        created_scenario = response.json()
        scenario_id = created_scenario['scenario_id']
        print(f"✅ Created scenario: {scenario_id} - {scenario_data['scenario_name']}")
        print(f"📊 Created scenario results:")
        print(f"   - Seniority years: {created_scenario['seniority_years']}")
        print(f"   - Grant gross: ₪{created_scenario['grant_gross']:,.2f}")
        print(f"   - Grant net: ₪{created_scenario['grant_net']:,.2f}")
        print(f"   - Monthly pension: ₪{created_scenario['pension_monthly']:,.2f}")
    else:
        print(f"❌ Failed to create scenario: {response.status_code} - {response.text}")
        return None
    
    # 2. List scenarios
    print(f"\n📋 Listing scenarios for client {client_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/clients/{client_id}/scenarios")
    
    if response.status_code == 200:
        scenarios_list = response.json()
        print(f"✅ Found {len(scenarios_list['scenarios'])} scenarios:")
        for scenario in scenarios_list['scenarios']:
            print(f"   - ID: {scenario['id']}, Name: {scenario['scenario_name']}, Created: {scenario['created_at']}")
    else:
        print(f"❌ Failed to list scenarios: {response.status_code} - {response.text}")
    
    # 3. Get specific scenario
    print(f"\n🔍 Retrieving scenario {scenario_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/clients/{client_id}/scenarios/{scenario_id}")
    
    if response.status_code == 200:
        retrieved_scenario = response.json()
        print(f"✅ Retrieved scenario successfully!")
        print(f"📊 Retrieved scenario results:")
        print(f"   - Seniority years: {retrieved_scenario['seniority_years']}")
        print(f"   - Grant gross: ₪{retrieved_scenario['grant_gross']:,.2f}")
        print(f"   - Grant net: ₪{retrieved_scenario['grant_net']:,.2f}")
        print(f"   - Monthly pension: ₪{retrieved_scenario['pension_monthly']:,.2f}")
        print(f"   - Cashflow points: {len(retrieved_scenario['cashflow'])}")
        
        # Verify data consistency
        if (created_scenario['seniority_years'] == retrieved_scenario['seniority_years'] and
            created_scenario['grant_gross'] == retrieved_scenario['grant_gross']):
            print("✅ Data consistency verified between create and retrieve!")
        else:
            print("❌ Data inconsistency detected!")
        
        return retrieved_scenario
    else:
        print(f"❌ Failed to retrieve scenario: {response.status_code} - {response.text}")
        return None

def main():
    print("🚀 Starting Scenario API Demo")
    print("=" * 50)
    
    # Create demo client
    client_id = create_demo_client()
    if not client_id:
        return
    
    # Create employment
    if not create_demo_employment(client_id):
        return
    
    # Test basic calculation
    calc_result = test_calculation_endpoint(client_id)
    if not calc_result:
        return
    
    # Test scenario persistence
    scenario_result = test_scenario_persistence(client_id)
    
    if scenario_result:
        print("\n" + "=" * 50)
        print("🎉 All scenario API tests completed successfully!")
        print("\n📄 Sample JSON Output (ScenarioOut):")
        print(json.dumps(scenario_result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Some tests failed")

if __name__ == "__main__":
    main()
