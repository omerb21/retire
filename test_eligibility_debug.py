#!/usr/bin/env python3
"""
בדיקת זכאות ישירה לדיבוג
"""
import requests
import json

def test_client_eligibility():
    """בדיקת זכאות לקוחות"""
    base_url = "http://localhost:8005"
    
    # בדיקת לקוח 1 (גבר בן 67 ללא קצבה)
    print("=== בדיקת לקוח 1 (גבר בן 67 ללא קצבה) ===")
    try:
        response = requests.post(f"{base_url}/api/v1/rights-fixation/calculate", 
                               json={"client_id": 1})
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Response: {response.text}")
        
        if response.status_code == 409:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif response.status_code == 500:
            print("Internal Server Error - checking server logs")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # בדיקת לקוח 2 (אישה בת 63 עם קצבה)
    print("=== בדיקת לקוח 2 (אישה בת 63 עם קצבה) ===")
    try:
        response = requests.post(f"{base_url}/api/v1/rights-fixation/calculate", 
                               json={"client_id": 2})
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response JSON (first 500 chars):")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_client_eligibility()
