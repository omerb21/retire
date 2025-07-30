#!/usr/bin/env python3
"""
Debug script to test ID validation logic
"""
from app.services.client_service import (
    validate_id_number, 
    normalize_id_number, 
    prepare_client_payload,
    validate_client_data
)

# Test data from the test file
test_id = "123456782"

print(f"Original ID: {test_id}")
print(f"Normalized ID: {normalize_id_number(test_id)}")
print(f"Is valid: {validate_id_number(test_id)}")
print(f"Is normalized valid: {validate_id_number(normalize_id_number(test_id))}")

# Test the full payload preparation
test_payload = {
    "id_number_raw": "123456782",
    "full_name": "ישראל ישראלי",
    "first_name": "ישראל",
    "last_name": "ישראלי",
    "birth_date": "1994-01-31",  # 30 years ago approximately
    "gender": "male",
    "marital_status": "single",
    "self_employed": False,
    "current_employer_exists": True,
    "planned_termination_date": "2025-01-31",  # 1 year from now
    "email": "user@example.com",
    "phone": "050-1234567",
    "address_street": "רחוב הרצל 1",
    "address_city": "תל אביב",
    "address_postal_code": "12345",
    "retirement_target_date": "2059-01-31",  # 35 years from now
    "is_active": True,
    "notes": "הערות לקוח"
}

print("\n--- Testing payload preparation ---")
prepared = prepare_client_payload(test_payload)
print(f"Prepared payload keys: {list(prepared.keys())}")
print(f"ID number in prepared: {prepared.get('id_number', 'NOT FOUND')}")

print("\n--- Testing validation ---")
errors = validate_client_data(prepared)
print(f"Validation errors: {errors}")
