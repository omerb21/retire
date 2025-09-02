"""
Test script to verify the fetch response handling works correctly
by simulating the frontend's API calls with Python requests
"""
import json
import requests
import sys
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"

def api_request(path, method="GET", data=None):
    """Simulate the frontend's fetch API with proper error handling"""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Check if response is successful
        response.raise_for_status()
        
        # Parse response based on content type
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return response.text
    
    except requests.exceptions.HTTPError as e:
        # Handle error response with proper content extraction
        try:
            if "application/json" in e.response.headers.get("Content-Type", ""):
                error_data = e.response.json()
                if isinstance(error_data, dict) and "detail" in error_data:
                    if isinstance(error_data["detail"], str):
                        error_message = error_data["detail"]
                    elif isinstance(error_data["detail"], list):
                        error_message = "; ".join(
                            d.get("msg", "") for d in error_data["detail"]
                        )
                    else:
                        error_message = str(error_data)
                else:
                    error_message = str(error_data)
            else:
                error_message = e.response.text
        except Exception:
            error_message = f"HTTP {e.response.status_code}"
        
        print(f"API Error: {error_message}")
        return {"error": error_message}
    
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        return {"error": f"Network error: {str(e)}"}

def test_list_clients():
    """Test listing clients"""
    print("\n----- Testing Client Listing -----")
    result = api_request("/clients?limit=10&offset=0")
    
    if "error" in result:
        print("✗ List clients failed")
        return False
    
    if "items" not in result:
        print("✗ List clients response missing 'items' field")
        return False
    
    print(f"✓ Successfully listed clients: {len(result['items'])} found")
    if result["items"]:
        print(f"First client: {json.dumps(result['items'][0], indent=2)}")
    return True

def test_create_client():
    """Test creating a new client"""
    print("\n----- Testing Client Creation -----")
    
    # Generate a unique test client
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    test_client = {
        "first_name": f"Test{timestamp[:6]}",
        "last_name": f"User{timestamp[6:]}",
        "id_number": "123456789",
        "birth_date": "1980-01-01",
        "email": f"test{timestamp}@example.com"
    }
    
    print(f"Creating client with data: {json.dumps(test_client, indent=2)}")
    result = api_request("/clients", method="POST", data=test_client)
    
    if "error" in result:
        print("✗ Client creation failed")
        return False
    
    if "id" not in result:
        print("✗ Client creation response missing 'id' field")
        return False
    
    print(f"✓ Successfully created client with ID: {result['id']}")
    print(f"Created client data: {json.dumps(result, indent=2)}")
    return True

def run_tests():
    """Run all tests and return True if all passed"""
    print("Starting API tests to verify fetch handling...")
    
    tests = [
        ("List Clients", test_list_clients),
        ("Create Client", test_create_client),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            print(f"\nRunning test: {name}")
            result = test_func()
            results.append(result)
            print(f"Test {name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"Test {name} raised exception: {str(e)}")
            results.append(False)
    
    success = all(results)
    print("\n----- Test Summary -----")
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")
    print(f"Overall result: {'SUCCESS' if success else 'FAILURE'}")
    
    return success

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
