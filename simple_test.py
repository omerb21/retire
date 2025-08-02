import requests
import json

try:
    response = requests.post('http://127.0.0.1:8000/api/v1/fixation/1/161d')
    print(f"Status Code: {response.status_code}")
    
    if response.headers.get('content-type', '').startswith('application/json'):
        data = response.json()
        print("Response JSON:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Response Text: {response.text}")
        
except Exception as e:
    print(f"Error: {e}")
