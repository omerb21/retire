#!/usr/bin/env python3
"""
Simple test script for Israeli ID validation
"""
from app.services.client_service import validate_id_number, normalize_id_number

# Test IDs
test_ids = [
    "123456782",  # Valid test case from code
    "305567663",  # Valid test case from code
    "012345672",  # Valid ID with checksum
    "123456789",  # Invalid checksum
]

for test_id in test_ids:
    normalized = normalize_id_number(test_id)
    is_valid = validate_id_number(test_id)
    print(f"ID: {test_id}, Normalized: {normalized}, Valid: {is_valid}")
