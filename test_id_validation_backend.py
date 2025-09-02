#!/usr/bin/env python3
"""
Comprehensive test script for Israeli ID validation
"""
from app.services.client_service import (
    validate_id_number, 
    normalize_id_number, 
    normalise_and_validate_id_number,
    prepare_client_payload
)

# Test a variety of ID formats
test_ids = [
    # Known valid test cases
    "123456782",  # Valid test case from code
    "305567663",  # Valid test case from code
    "012345672",  # Valid ID with checksum
    
    # Different formats of the same valid ID
    "123-456-782",
    " 123456782 ",
    "0123456782",  # Extra leading zero
    
    # Invalid IDs
    "123456789",  # Invalid checksum
    "12345678",   # Too short
    "1234567890",  # Too long
    "",           # Empty
    None,         # None
]

print("=== Testing ID Validation ===\n")
print(f"{'ID Input':<15} | {'Normalized':<12} | {'Valid?':<6} | {'Valid After Norm?':<16}")
print("-" * 55)

for test_id in test_ids:
    try:
        normalized = normalize_id_number(test_id)
        is_valid = validate_id_number(test_id)
        is_normalized_valid = validate_id_number(normalized)
        
        # Also test the combined function
        norm_result, norm_valid = normalise_and_validate_id_number(test_id) if test_id else ("", False)
        
        print(f"{str(test_id):<15} | {normalized:<12} | {str(is_valid):<6} | {str(is_normalized_valid):<16} | Combined: {norm_valid}")
    except Exception as e:
        print(f"{str(test_id):<15} | ERROR: {str(e)}")

print("\n=== Testing Client Payload Preparation ===\n")

# Test with valid ID
try:
    valid_payload = {
        "id_number_raw": "123456782",
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "birth_date": "1990-01-01"
    }
    
    prepared = prepare_client_payload(valid_payload)
    print(f"Valid ID payload preparation: SUCCESS")
    print(f"  id_number: {prepared.get('id_number')}")
    print(f"  id_number_raw: {prepared.get('id_number_raw')}")
except Exception as e:
    print(f"Valid ID payload preparation: FAILED - {str(e)}")

# Test with invalid ID
try:
    invalid_payload = {
        "id_number_raw": "123456789",  # Invalid checksum
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "birth_date": "1990-01-01"
    }
    
    prepared = prepare_client_payload(invalid_payload)
    print(f"Invalid ID payload preparation: UNEXPECTED SUCCESS")
except Exception as e:
    print(f"Invalid ID payload preparation: EXPECTED FAILURE - {str(e)}")

print("\n=== Testing Frontend-like Payload ===\n")

# Test with payload similar to what frontend would send
try:
    frontend_payload = {
        "id_number": "123456782",  # Valid ID in id_number field
        "first_name": "ישראל",
        "last_name": "ישראלי",
        "birth_date": "1990-01-01"
    }
    
    prepared = prepare_client_payload(frontend_payload)
    print(f"Frontend payload preparation: SUCCESS")
    print(f"  id_number: {prepared.get('id_number')}")
    print(f"  id_number_raw: {prepared.get('id_number_raw', 'NOT SET')}")
except Exception as e:
    print(f"Frontend payload preparation: FAILED - {str(e)}")
