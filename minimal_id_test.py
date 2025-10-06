#!/usr/bin/env python3
"""
Minimal test script for client creation with ID validation
"""
import requests
import json

# Test with known valid IDs
valid_ids = [
    "123456782",  # Valid test case from code
    "305567663",  # Valid test case from code
    "012345672",  # Valid ID with checksum
]

# Base URL for API
base_url = "http://127.0.0.1:8000/api/v1"

for test_id in valid_ids:
    # Create a minimal client payload
    client_data = {
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "id_number": test_id,
        "id_number_raw": test_id,
        "birth_date": "1990-01-01"
    }
    
    print(f"\nTesting with ID: {test_id}")
    print(f"Sending payload: {json.dumps(client_data)}")
    
    try:
        # Send POST request to create client
        response = requests.post(
            f"{base_url}/clients", 
            json=client_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            print("✅ Success! Client created.")
            print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        else:
            print("❌ Failed to create client.")
            print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")
