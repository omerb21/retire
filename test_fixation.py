import requests
import json

def test_fixation():
    try:
        url = "http://localhost:8005/api/v1/rights-fixation/calculate"
        data = {"client_id": 1}
        
        print(f"Sending request to: {url}")
        print(f"Data: {data}")
        
        response = requests.post(url, json=data)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Found {len(result.get('grants', []))} grants")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_fixation()
