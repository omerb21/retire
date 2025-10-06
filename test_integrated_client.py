"""
Integrated test client that doesn't depend on external server
Uses FastAPI TestClient for reliable testing without port/CORS issues
"""
import json
import hashlib
import base64
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app

# Create test client
client = TestClient(app)

def test_health_endpoint():
    """Test basic health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    print("✓ Health endpoint working")

def test_case_detection_post():
    """Test case detection POST endpoint"""
    response = client.post("/api/v1/clients/1/case/detect")
    print(f"Case detection POST: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Case detection returned: {data}")
        return True
    else:
        print(f"✗ Case detection failed: {response.text}")
        return False

def test_scenario_compare():
    """Test scenario compare endpoint"""
    payload = {
        "scenarios": [1, 2],
        "from": "2025-01",
        "to": "2025-12",
        "frequency": "monthly"
    }
    
    response = client.post("/api/v1/clients/1/scenarios/compare", json=payload)
    print(f"Scenario compare: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        print(f"✓ Compare returned {len(results)} scenarios")
        
        # Check yearly totals exist
        for result in results:
            yearly = result.get("yearly", {})
            if yearly:
                print(f"✓ Scenario {result['scenario_id']} has yearly totals: {list(yearly.keys())}")
            else:
                print(f"⚠ Scenario {result['scenario_id']} missing yearly totals")
        return True
    else:
        print(f"✗ Scenario compare failed: {response.text}")
        return False

def test_pdf_generation():
    """Test PDF report generation"""
    payload = {
        "from_": "2025-01",
        "to": "2025-12",
        "sections": ["summary", "cashflow", "charts"]
    }
    
    response = client.post("/api/v1/scenarios/1/report/pdf?client_id=1", json=payload)
    print(f"PDF generation: {response.status_code}")
    if response.status_code == 200:
        content = response.content
        if content.startswith(b'%PDF'):
            print(f"✓ PDF generated successfully ({len(content)} bytes)")
            # Calculate hash for verification
            pdf_hash = hashlib.sha256(content).hexdigest()
            pdf_b64 = base64.b64encode(content[:100]).decode()
            print(f"PDF hash: {pdf_hash[:16]}...")
            print(f"PDF header (base64): {pdf_b64}")
            return True
        else:
            print(f"✗ Invalid PDF content")
            return False
    else:
        print(f"✗ PDF generation failed: {response.text}")
        return False

def run_integrated_tests():
    """Run all integrated tests"""
    print("=== INTEGRATED API TESTS ===")
    print(f"Test time: {datetime.now().isoformat()}")
    
    tests = [
        ("Health Check", test_health_endpoint),
        ("Case Detection POST", test_case_detection_post),
        ("Scenario Compare", test_scenario_compare),
        ("PDF Generation", test_pdf_generation)
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    print("\n=== TEST SUMMARY ===")
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready.")
    else:
        print("⚠ Some tests failed. Check the issues above.")
    
    return passed == total

if __name__ == "__main__":
    run_integrated_tests()
