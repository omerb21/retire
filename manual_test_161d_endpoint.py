#!/usr/bin/env python3
"""
Script to test 161d endpoint
"""
import requests
import json

def test_161d_endpoint():
    """Test the 161d endpoint"""
    print("Testing 161d endpoint...")
    
    url = "http://127.0.0.1:8000/api/v1/fixation/1/161d"
    
    try:
        response = requests.post(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            data = response.json()
            print(f"Response JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
        else:
            print(f"Response Text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure the server is running on http://127.0.0.1:8000")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_161d_endpoint()
