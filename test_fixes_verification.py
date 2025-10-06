#!/usr/bin/env python3
"""
Test script to verify the fixes for:
1. JSON serialization error with date objects in HTTPException
2. Grants display issue in frontend
"""

import requests
import json

def test_api_endpoints():
    """Test the backend API endpoints"""
    base_url = "http://localhost:8005"
    
    print("=== Testing Backend API Endpoints ===")
    
    # Test 1: Get client grants (should work)
    print("\n1. Testing client grants endpoint...")
    try:
        response = requests.get(f"{base_url}/api/v1/clients/1/grants")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            grants = response.json()
            print(f"Found {len(grants)} grants for client 1")
            for grant in grants:
                print(f"  - Grant {grant['id']}: {grant['grant_amount']} from {grant['employer_name']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Rights fixation for eligible client (client 2)
    print("\n2. Testing rights fixation for eligible client (client 2)...")
    try:
        response = requests.post(f"{base_url}/api/v1/rights-fixation/calculate", 
                               json={"client_id": 2})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✓ Rights fixation calculation successful")
            print(f"  - Grants processed: {len(data.get('grants', []))}")
            print(f"  - Eligibility date: {data.get('eligibility_date', 'N/A')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Rights fixation for ineligible client (client 1) - should return 409
    print("\n3. Testing rights fixation for ineligible client (client 1)...")
    try:
        response = requests.post(f"{base_url}/api/v1/rights-fixation/calculate", 
                               json={"client_id": 1})
        print(f"Status: {response.status_code}")
        if response.status_code == 409:
            data = response.json()
            print("✓ Eligibility check working correctly (409 error)")
            print(f"  - Error: {data.get('error', 'N/A')}")
            print(f"  - Reasons: {data.get('reasons', [])}")
            print(f"  - Eligibility date: {data.get('eligibility_date', 'N/A')}")
            # Test that JSON serialization works (no date objects causing errors)
            json_str = json.dumps(data)
            print("✓ JSON serialization working correctly")
        else:
            print(f"Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api_endpoints()
