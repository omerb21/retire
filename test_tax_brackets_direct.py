#!/usr/bin/env python3
"""
Test tax brackets API directly
"""
import sys
import os
sys.path.append(os.getcwd())

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

try:
    print("Testing tax brackets endpoint directly...")
    response = client.get("/api/v1/tax-data/tax-brackets")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {response.json()}")
    else:
        print(f"Error response: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
