"""
Minimal test script for client creation with id_number field
"""
import requests
import json

def test_client_api():
    """Test client creation using id_number field"""
    try:
        print("Testing API endpoint...")
        # URL for creating clients
        url = "http://localhost:8000/api/v1/clients"
        
        # Test data using id_number instead of id_number_raw
        test_data = {
            "first_name": "Test",
            "last_name": "User",
            "id_number": "123456782",  # Valid ID for testing
            "birth_date": "1980-01-01"
        }
        
        print(f"Sending POST request to {url} with data:")
        print(json.dumps(test_data, indent=2))
        
        # Create client
        response = requests.post(url, json=test_data)
        print(f"Response status code: {response.status_code}")
        
        # Check response
        if response.status_code in (200, 201):
            print("Client created successfully!")
            client = response.json()
            print(f"Client ID: {client.get('id')}")
            print(f"Client Name: {client.get('first_name')} {client.get('last_name')}")
            print(f"Client ID Number: {client.get('id_number')}")
            
            # Now fetch the client to verify it was created
            client_id = client.get('id')
            if client_id:
                print(f"\nFetching client with ID {client_id}...")
                get_url = f"{url}/{client_id}"
                get_response = requests.get(get_url)
                
                if get_response.status_code == 200:
                    fetched_client = get_response.json()
                    print("Client successfully retrieved!")
                    print(f"Retrieved client ID number: {fetched_client.get('id_number')}")
                else:
                    print(f"Error fetching client: {get_response.status_code}")
                    print(get_response.text)
        else:
            print(f"Error creating client: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Exception occurred: {e}")

if __name__ == "__main__":
    test_client_api()
