#!/usr/bin/env python
"""Check if routes are loaded in the live server"""
import requests
import json

# Get all routes from FastAPI's OpenAPI schema
try:
    response = requests.get("http://localhost:8005/openapi.json")
    if response.status_code == 200:
        schema = response.json()
        paths = schema.get("paths", {})
        
        print("=" * 70)
        print("CHECKING RETIREMENT SCENARIOS ENDPOINT")
        print("=" * 70)
        
        # Look for retirement-scenarios
        found = False
        for path, methods in paths.items():
            if "retirement-scenarios" in path:
                print(f"\n✅ FOUND: {path}")
                for method, details in methods.items():
                    print(f"   Method: {method.upper()}")
                    print(f"   Summary: {details.get('summary', 'N/A')}")
                found = True
        
        if not found:
            print("\n❌ NOT FOUND: /retirement-scenarios endpoint missing!")
            print("\n📋 Available /clients endpoints:")
            for path in sorted(paths.keys()):
                if "/clients/" in path:
                    print(f"   {path}")
    else:
        print(f"❌ Failed to get OpenAPI schema: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")
