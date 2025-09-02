"""
Simple script to test client API endpoints
"""
import requests
import json
from datetime import date
import sys

BASE_URL = "http://localhost:8000/api/v1"

def test_create_client():
    """Test creating a new client with id_number instead of id_number_raw"""
    url = f"{BASE_URL}/clients"
    
    # Client data using id_number field with valid Israeli ID
    client_data = {
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "id_number": "123456782", # Valid test ID
        "birth_date": "1980-01-01",
        "email": "test@example.com",
        "phone": "0501234567"
    }
    
    try:
        response = requests.post(url, json=client_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("Client created successfully!")
            print(json.dumps(response.json(), indent=2))
            return response.json()
        else:
            print(f"Error creating client: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def test_list_clients():
    """Test listing clients"""
    url = f"{BASE_URL}/clients"
    
    try:
        response = requests.get(url)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            clients = response.json()
            print(f"Total clients: {clients['total']}")
            print("Clients:")
            for client in clients['items']:
                print(f"  - {client['id']}: {client.get('first_name', '')} {client.get('last_name', '')} ({client.get('id_number', '')})")
            return clients
        else:
            print(f"Error listing clients: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def test_create_client_with_another_id():
    """Test creating a client with another valid ID"""
    url = f"{BASE_URL}/clients"
    
    # Client data using another valid Israeli ID
    client_data = {
        "first_name": "משה",
        "last_name": "כהן",
        "id_number": "305567663", # Another valid test ID
        "birth_date": "1990-05-15",
        "email": "moshe@example.com",
        "phone": "0521234567"
    }
    
    try:
        response = requests.post(url, json=client_data)
        print(f"\nStatus Code for second client: {response.status_code}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("Second client created successfully!")
            print(json.dumps(response.json(), indent=2))
            return response.json()
        else:
            print(f"Error creating second client: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

if __name__ == "__main__":
    print("Testing client API...")
    print("\n1. Testing backend server connection...")
    
    try:
        # Test server connection first
        health_check = requests.get(f"{BASE_URL}/health")
        print(f"Backend server health check: {health_check.status_code}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to backend server at http://localhost:8000")
        print("Please make sure the backend server is running with:")
        print("uvicorn app.main:app --reload")
        sys.exit(1)
    
    print("\n2. Creating first client...")
    new_client = test_create_client()
    
    print("\n3. Creating second client with different ID...")
    second_client = test_create_client_with_another_id()
    
    print("\n4. Listing all clients...")
    test_list_clients()
