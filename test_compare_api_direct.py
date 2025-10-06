#!/usr/bin/env python3
"""Direct test of compare API to verify 12 months are returned"""

import requests
import json
import sys

def test_compare_api():
    """Test compare API directly"""
    url = "http://127.0.0.1:8000/api/v1/clients/1/scenarios/compare"
    
    payload = {
        "scenarios": [24],
        "from": "2025-01", 
        "to": "2025-12",
        "frequency": "monthly"
    }
    
    headers = {"Content-Type": "application/json"}
    
    print("Testing compare API...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'scenarios' in data and len(data['scenarios']) > 0:
                scenario = data['scenarios'][0]
                monthly_data = scenario.get('monthly', [])
                
                print(f"✓ API Response OK")
                print(f"✓ Scenarios returned: {len(data['scenarios'])}")
                print(f"✓ Monthly data rows: {len(monthly_data)}")
                
                if len(monthly_data) == 12:
                    print("✓ SUCCESS: 12 months returned as expected")
                    
                    # Show first few and last few months
                    print("\nFirst 3 months:")
                    for i in range(min(3, len(monthly_data))):
                        row = monthly_data[i]
                        print(f"  {i+1}: {row.get('date')} | net={row.get('net', 0)}")
                    
                    print("\nLast 3 months:")
                    for i in range(max(0, len(monthly_data)-3), len(monthly_data)):
                        row = monthly_data[i]
                        print(f"  {i+1}: {row.get('date')} | net={row.get('net', 0)}")
                        
                    # Check yearly totals
                    yearly_totals = scenario.get('yearly_totals', {})
                    if '2025' in yearly_totals:
                        totals = yearly_totals['2025']
                        print(f"\nYearly totals for 2025:")
                        print(f"  inflow: {totals.get('inflow', 0)}")
                        print(f"  outflow: {totals.get('outflow', 0)}")
                        print(f"  additional_income_net: {totals.get('additional_income_net', 0)}")
                        print(f"  capital_return_net: {totals.get('capital_return_net', 0)}")
                        print(f"  net: {totals.get('net', 0)}")
                    
                    return True
                else:
                    print(f"✗ FAIL: Expected 12 months, got {len(monthly_data)}")
                    print("Monthly data dates:")
                    for i, row in enumerate(monthly_data):
                        print(f"  {i+1}: {row.get('date')}")
                    return False
            else:
                print("✗ No scenarios in response")
                print(f"Response: {json.dumps(data, indent=2)}")
                return False
        else:
            print(f"✗ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection Error: Cannot connect to API server")
        print("Make sure the server is running on http://127.0.0.1:8000")
        return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

def test_health():
    """Test if API server is responding"""
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✓ API server is responding")
            return True
        else:
            print(f"✗ API server returned {response.status_code}")
            return False
    except:
        print("✗ API server is not responding")
        return False

if __name__ == "__main__":
    print("=== DIRECT COMPARE API TEST ===")
    
    # Test server health first
    if not test_health():
        print("Server is not running. Start it with:")
        print("python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload")
        sys.exit(1)
    
    # Test compare API
    success = test_compare_api()
    
    if success:
        print("\n✓ SUCCESS: Compare API returns 12 months correctly")
        sys.exit(0)
    else:
        print("\n✗ FAIL: Compare API is not returning 12 months")
        sys.exit(1)
