"""
Direct API test script for client creation
"""
import requests
import json
from datetime import datetime, date, timedelta

# API endpoint
API_URL = "http://localhost:8000/api/v1/clients"

def test_create_client():
    """Test creating a client with valid data"""
    
    # Client data with valid Israeli ID
    client_data = {
        "id_number": "123456782",  # Valid test ID
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "birth_date": "1980-01-01",
        "email": "test@example.com",
        "phone": "0501234567"
    }
    
    print(f"Sending client data: {json.dumps(client_data, indent=2, ensure_ascii=False)}")
    
    try:
        # Send POST request to create client
        response = requests.post(API_URL, json=client_data)
        
        # Print response status and content
        print(f"Status code: {response.status_code}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("Client created successfully!")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Error creating client: {response.text}")
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")

def test_create_client_with_another_id():
    """Test creating a client with another valid ID"""
    
    # Client data with another valid Israeli ID
    client_data = {
        "id_number": "305567663",  # Another valid test ID
        "first_name": "משה",
        "last_name": "כהן",
        "birth_date": "1990-05-15",
        "email": "moshe@example.com",
        "phone": "0521234567"
    }
    
    print(f"\nSending another client data: {json.dumps(client_data, indent=2, ensure_ascii=False)}")
    
    try:
        # Send POST request to create client
        response = requests.post(API_URL, json=client_data)
        
        # Print response status and content
        print(f"Status code: {response.status_code}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("Client created successfully!")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Error creating client: {response.text}")
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")

def test_list_clients():
    """Test listing all clients"""
    
    print("\nListing all clients:")
    
    try:
        # Send GET request to list clients
        response = requests.get(API_URL)
        
        # Print response status and content
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            clients = response.json()
            print(f"Total clients: {clients.get('total', 0)}")
            
            if clients.get('items'):
                for i, client in enumerate(clients['items']):
                    print(f"{i+1}. {client.get('first_name', '')} {client.get('last_name', '')} - {client.get('id_number', '')}")
            else:
                print("No clients found.")
        else:
            print(f"Error listing clients: {response.text}")
            
    except Exception as e:
        print(f"Exception occurred: {str(e)}")

def test_birth_date_validation():
    """Test birth date validation (age between 18-120)"""
    
    today = date.today()
    
    # Test with birth date less than 18 years ago (too young)
    too_young_date = (today - timedelta(days=17*365)).isoformat()
    
    # Test with birth date more than 120 years ago (too old)
    too_old_date = (today - timedelta(days=121*365)).isoformat()
    
    # Test case 1: Too young
    print("\nTesting birth date validation - too young:")
    client_data = {
        "id_number": "123456782",
        "first_name": "צעיר",
        "last_name": "מדי",
        "birth_date": too_young_date,
        "email": "young@example.com"
    }
    
    try:
        response = requests.post(API_URL, json=client_data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code >= 400:
            print("✓ Validation correctly rejected too young birth date")
        else:
            print("✗ Validation failed - accepted too young birth date")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
    
    # Test case 2: Too old
    print("\nTesting birth date validation - too old:")
    client_data = {
        "id_number": "123456782",
        "first_name": "זקן",
        "last_name": "מדי",
        "birth_date": too_old_date,
        "email": "old@example.com"
    }
    
    try:
        response = requests.post(API_URL, json=client_data)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
        if response.status_code >= 400:
            print("✓ Validation correctly rejected too old birth date")
        else:
            print("✗ Validation failed - accepted too old birth date")
    except Exception as e:
        print(f"Exception occurred: {str(e)}")


if __name__ == "__main__":
    print("=" * 50)
    print(f"API TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Test server connection
    try:
        health = requests.get("http://localhost:8000/api/v1/health")
        print(f"Server health check: {health.status_code}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to backend server at http://localhost:8000")
        print("Please make sure the backend server is running with:")
        print("uvicorn app.main:app --reload")
        exit(1)
    
    # Run tests
    test_create_client()
    test_create_client_with_another_id()
    test_birth_date_validation()
    test_list_clients()
