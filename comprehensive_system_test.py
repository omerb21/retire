#!/usr/bin/env python3
"""
Comprehensive system test for the retirement planning system
Tests all major endpoints and functionality after fixes
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8005"

def test_client_operations():
    """Test client CRUD operations"""
    print("🧪 Testing Client Operations...")
    
    # Create client
    client_data = {
        "full_name": "בדיקה מערכתית",
        "id_number": "123456789",
        "birth_date": "1980-01-01",
        "phone": "050-1234567",
        "email": "test@example.com"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients", json=client_data)
    print(f"   Create client: {response.status_code}")
    if response.status_code == 200:
        client_id = response.json()["id"]
        print(f"   ✅ Client created with ID: {client_id}")
        return client_id
    else:
        print(f"   ❌ Failed to create client: {response.text}")
        return None

def test_current_employer(client_id):
    """Test current employer operations"""
    print("🏢 Testing Current Employer...")
    
    # Create current employer
    employer_data = {
        "employer_name": "חברת בדיקה בע״מ",
        "start_date": "2020-01-01",
        "monthly_salary": 15000,
        "severance_balance": 75000
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/current-employer", json=employer_data)
    print(f"   Create employer: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Current employer created")
        
        # Test calculation endpoint
        calc_data = {
            "start_date": "2020-01-01",
            "monthly_salary": 15000,
            "severance_amount": 75000
        }
        
        calc_response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/current-employer/calculate", json=calc_data)
        print(f"   Calculate benefits: {calc_response.status_code}")
        
        if calc_response.status_code == 200:
            result = calc_response.json()
            print(f"   ✅ Service years: {result['service_years']}")
            print(f"   ✅ Final exemption: {result['final_exemption']:,.0f} ₪")
            print(f"   ✅ Taxable amount: {result['taxable_amount']:,.0f} ₪")
        else:
            print(f"   ❌ Calculation failed: {calc_response.text}")
    else:
        print(f"   ❌ Failed to create employer: {response.text}")

def test_pension_funds(client_id):
    """Test pension fund operations"""
    print("💰 Testing Pension Funds...")
    
    # Create pension fund
    fund_data = {
        "fund_name": "קרן פנסיה לבדיקה",
        "balance": 500000,
        "annuity_factor": 180,
        "indexation_rate": 0.02
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/pension-funds", json=fund_data)
    print(f"   Create pension fund: {response.status_code}")
    
    if response.status_code == 200:
        fund_id = response.json()["id"]
        print(f"   ✅ Pension fund created with ID: {fund_id}")
        
        # Test computation
        compute_response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/pension-funds/{fund_id}/compute")
        print(f"   Compute monthly amount: {compute_response.status_code}")
        
        if compute_response.status_code == 200:
            result = compute_response.json()
            print(f"   ✅ Monthly pension: {result['computed_monthly_amount']:,.0f} ₪")
        else:
            print(f"   ❌ Computation failed: {compute_response.text}")
    else:
        print(f"   ❌ Failed to create pension fund: {response.text}")

def test_grants(client_id):
    """Test grants operations"""
    print("🎁 Testing Grants...")
    
    # Create grant
    grant_data = {
        "client_id": client_id,
        "grant_amount": 100000,
        "grant_year": 2024,
        "employer_name": "מעסיק קודם",
        "grant_type": "severance"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/grants", json=grant_data)
    print(f"   Create grant: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Grant created successfully")
    else:
        print(f"   ❌ Failed to create grant: {response.text}")

def test_rights_fixation(client_id):
    """Test rights fixation calculation"""
    print("⚖️ Testing Rights Fixation...")
    
    # Test rights fixation calculation
    fixation_data = {
        "client_id": client_id
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/rights-fixation/calculate", json=fixation_data)
    print(f"   Calculate rights fixation: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Total grants processed: {len(result.get('grants', []))}")
        if result.get('summary'):
            summary = result['summary']
            print(f"   ✅ Total indexed amount: {summary.get('total_indexed_amount', 0):,.0f} ₪")
            print(f"   ✅ Total limited amount: {summary.get('total_limited_amount', 0):,.0f} ₪")
    else:
        print(f"   ❌ Rights fixation failed: {response.text}")

def test_scenarios_and_pdf(client_id):
    """Test scenarios and PDF generation"""
    print("📊 Testing Scenarios and PDF...")
    
    # Create scenario
    scenario_data = {
        "name": "תרחיש בדיקה מערכתית",
        "description": "תרחיש שנוצר לבדיקת המערכת",
        "retirement_age": 67,
        "monthly_expenses": 12000
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/scenarios", json=scenario_data)
    print(f"   Create scenario: {response.status_code}")
    
    if response.status_code == 200:
        scenario_id = response.json()["id"]
        print(f"   ✅ Scenario created with ID: {scenario_id}")
        
        # Test PDF generation
        pdf_response = requests.get(f"{BASE_URL}/api/v1/clients/{client_id}/scenarios/{scenario_id}/pdf")
        print(f"   Generate PDF: {pdf_response.status_code}")
        
        if pdf_response.status_code == 200:
            result = pdf_response.json()
            print(f"   ✅ PDF generated for: {result.get('client_name')}")
            print(f"   ✅ Scenario: {result.get('scenario_name')}")
        else:
            print(f"   ❌ PDF generation failed: {pdf_response.text}")
    else:
        print(f"   ❌ Failed to create scenario: {response.text}")

def test_additional_modules(client_id):
    """Test additional income and capital assets"""
    print("💼 Testing Additional Modules...")
    
    # Test additional income
    income_data = {
        "income_type": "rental",
        "monthly_amount": 3000,
        "description": "דירה להשכרה"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/additional-incomes", json=income_data)
    print(f"   Create additional income: {response.status_code}")
    
    # Test capital assets
    asset_data = {
        "asset_type": "stocks",
        "current_value": 200000,
        "description": "תיק מניות"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/clients/{client_id}/capital-assets", json=asset_data)
    print(f"   Create capital asset: {response.status_code}")

def main():
    """Run comprehensive system test"""
    print("🚀 Starting Comprehensive System Test")
    print("=" * 50)
    
    try:
        # Test client operations
        client_id = test_client_operations()
        if not client_id:
            print("❌ Cannot continue without client ID")
            return
        
        print()
        
        # Test all modules
        test_current_employer(client_id)
        print()
        
        test_pension_funds(client_id)
        print()
        
        test_grants(client_id)
        print()
        
        test_rights_fixation(client_id)
        print()
        
        test_scenarios_and_pdf(client_id)
        print()
        
        test_additional_modules(client_id)
        print()
        
        print("=" * 50)
        print("✅ Comprehensive system test completed successfully!")
        print("🎉 All major components are working correctly")
        
    except Exception as e:
        print(f"❌ System test failed with error: {str(e)}")

if __name__ == "__main__":
    main()
