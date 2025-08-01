#!/usr/bin/env python3
"""
Quick test script for rights fixation endpoints
"""
import requests
import json
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base
from app.models.client import Client

# Create test client
client = TestClient(app)

def test_endpoints_availability():
    """Test that all fixation endpoints are available"""
    print("Testing fixation endpoints availability...")
    
    # Test with a non-existent client ID (should return 404)
    test_client_id = 99999
    
    endpoints = [
        f"/api/v1/fixation/{test_client_id}/161d",
        f"/api/v1/fixation/{test_client_id}/grants-appendix", 
        f"/api/v1/fixation/{test_client_id}/commutations-appendix",
        f"/api/v1/fixation/{test_client_id}/package"
    ]
    
    for endpoint in endpoints:
        try:
            response = client.post(endpoint)
            print(f"✅ {endpoint}: Status {response.status_code}")
            
            if response.status_code == 404:
                data = response.json()
                if "לקוח לא נמצא" in data.get("detail", {}).get("error", ""):
                    print(f"   Hebrew error message working: {data['detail']['error']}")
            
        except Exception as e:
            print(f"❌ {endpoint}: Error - {e}")

def test_with_real_client():
    """Test with a real client in the database"""
    print("\nTesting with real client...")
    
    # Create in-memory database for this test
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    
    # Override get_db for this test
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Create a test client
    db = SessionLocal()
    try:
        test_client_obj = Client(
            id_number_raw="123456782",
            id_number="123456782", 
            full_name="ישראל ישראלי",
            first_name="ישראל",
            last_name="ישראלי",
            birth_date=date(1980, 1, 1),
            is_active=True
        )
        db.add(test_client_obj)
        db.commit()
        db.refresh(test_client_obj)
        client_id = test_client_obj.id
        
        print(f"Created test client with ID: {client_id}")
        
        # Test endpoints with real client
        response = client.post(f"/api/v1/fixation/{client_id}/161d")
        print(f"161d endpoint: Status {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success response: {data.get('message', 'No message')}")
        elif response.status_code == 500:
            data = response.json()
            print(f"Expected error (no real fixation system): {data.get('detail', {}).get('error', 'Unknown error')}")
        
    finally:
        db.close()
        # Clean up override
        app.dependency_overrides.clear()

if __name__ == "__main__":
    print("🔧 Testing Rights Fixation API Integration")
    print("=" * 50)
    
    test_endpoints_availability()
    test_with_real_client()
    
    print("\n✅ Basic integration tests completed!")
    print("Note: Full functionality requires the rights fixation system to be properly configured.")
