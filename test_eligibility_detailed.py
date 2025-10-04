#!/usr/bin/env python3
"""
Test detailed eligibility logic
"""

import requests
import json
from datetime import datetime, date

def test_eligibility_detailed():
    """Test current eligibility logic with detailed analysis"""
    clients_to_test = [1, 2, 3, 4, 5, 6]

    for client_id in clients_to_test:
        print(f'\n=== Testing Client {client_id} ===')
        
        # Get client data first
        try:
            client_resp = requests.get(f'http://localhost:8005/api/v1/clients/{client_id}')
            if client_resp.status_code == 200:
                client = client_resp.json()
                print(f'Client: {client.get("first_name", "")} {client.get("last_name", "")}')
                print(f'Birth date: {client.get("birth_date", "N/A")}')
                print(f'Gender: {client.get("gender", "N/A")}')
                print(f'Pension start: {client.get("pension_start_date", "N/A")}')
                
                # Calculate age
                if client.get('birth_date'):
                    birth_date = datetime.strptime(client['birth_date'], '%Y-%m-%d').date()
                    today = date.today()
                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                    print(f'Current age: {age}')
                    
                    # Check eligibility requirements
                    gender = client.get('gender', '').lower()
                    required_age = 67 if gender in ['male', 'm', 'זכר'] else 62
                    print(f'Required age: {required_age}')
                    print(f'Age eligible: {age >= required_age}')
                    
                    has_pension = bool(client.get('pension_start_date'))
                    print(f'Has pension start date: {has_pension}')
            
            # Test rights fixation
            resp = requests.post(f'http://localhost:8005/api/v1/rights-fixation/calculate', 
                               json={'client_id': client_id})
            print(f'Rights fixation status: {resp.status_code}')
            
            if resp.status_code == 409:
                error_data = resp.json().get('detail', {})
                print(f'Eligibility error: {error_data.get("error", "N/A")}')
                print(f'Reasons: {error_data.get("reasons", [])}')
            elif resp.status_code == 200:
                print('Rights fixation calculation successful')
            else:
                print(f'Unexpected response: {resp.text}')
                
        except Exception as e:
            print(f'Error testing client {client_id}: {e}')

if __name__ == "__main__":
    test_eligibility_detailed()
