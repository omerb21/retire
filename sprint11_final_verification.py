"""
Final Sprint 11 verification script with integrated testing
No external server dependencies - uses FastAPI TestClient
"""
import json
import hashlib
import base64
import zipfile
import os
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient

def create_test_client():
    """Create test client with proper error handling"""
    try:
        from app.main import app
        return TestClient(app)
    except Exception as e:
        print(f"Failed to create test client: {e}")
        return None

def generate_nonce():
    """Generate cryptographic nonce"""
    import secrets
    return secrets.token_hex(16)

def test_case_detection(client):
    """Test case detection POST endpoint"""
    print("Testing CASE DETECT endpoint...")
    
    response = client.post("/api/v1/clients/1/case/detect")
    if response.status_code == 200:
        data = response.json()
        case_value = data.get("case", "")
        print(f"✓ CASE DETECT: {response.status_code} - case: {case_value}")
        return True, case_value
    else:
        print(f"✗ CASE DETECT: {response.status_code} - {response.text}")
        return False, None

def test_scenario_compare(client):
    """Test scenario compare endpoint"""
    print("Testing COMPARE endpoint...")
    
    payload = {
        "scenarios": [1, 2],
        "from": "2025-01", 
        "to": "2025-12",
        "frequency": "monthly"
    }
    
    response = client.post("/api/v1/clients/1/scenarios/compare", json=payload)
    if response.status_code == 200:
        data = response.json()
        results = data.get("results", [])
        
        yearly_available = False
        for result in results:
            yearly = result.get("yearly", {})
            if yearly:
                yearly_available = True
                break
        
        status = "yearly totals available" if yearly_available else "yearly totals unavailable"
        print(f"✓ COMPARE: {response.status_code} - {status}")
        return True, yearly_available
    else:
        print(f"✗ COMPARE: {response.status_code} - {response.text}")
        return False, False

def test_pdf_generation(client):
    """Test PDF generation endpoint"""
    print("Testing PDF generation...")
    
    payload = {
        "from_": "2025-01",
        "to": "2025-12", 
        "sections": ["summary", "cashflow"]
    }
    
    response = client.post("/api/v1/scenarios/1/report/pdf?client_id=1", json=payload)
    if response.status_code == 200:
        content = response.content
        if content.startswith(b'%PDF'):
            size = len(content)
            pdf_hash = hashlib.sha256(content).hexdigest()
            head_b64 = base64.b64encode(content[:100]).decode()
            print(f"✓ PDF: {response.status_code} - {size} bytes, hash: {pdf_hash[:16]}...")
            return True, size, pdf_hash, head_b64
        else:
            print(f"✗ PDF: Invalid content (not PDF)")
            return False, 0, "", ""
    else:
        print(f"✗ PDF: {response.status_code} - {response.text}")
        return False, 0, "", ""

def create_proof_archive():
    """Create proof archive with verification results"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    archive_name = f"artifacts/release-{timestamp}-s11.zip"
    
    # Ensure artifacts directory exists
    os.makedirs("artifacts", exist_ok=True)
    
    # Create archive
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add verification script
        zf.write(__file__, "sprint11_verification.py")
        
        # Add key source files
        key_files = [
            "app/main.py",
            "app/routers/case_detection.py", 
            "app/routers/scenario_compare.py",
            "app/routers/report_generation.py",
            "app/services/compare_service.py",
            "app/services/report_service.py",
            "app/utils/contract_adapter.py",
            "app/utils/date_serializer.py"
        ]
        
        for file_path in key_files:
            if os.path.exists(file_path):
                zf.write(file_path, file_path)
    
    # Get archive size
    archive_size = os.path.getsize(archive_name)
    return archive_name, archive_size

def main():
    """Main verification function"""
    nonce = generate_nonce()
    start_time = datetime.now()
    
    print("=== SPRINT 11 PROOF SUMMARY ===")
    print(f"NONCE: {nonce}")
    print(f"TIMESTAMP: {start_time.isoformat()}")
    print()
    
    # Create test client
    client = create_test_client()
    if not client:
        print("✗ Failed to create test client")
        print("=== END SUMMARY ===")
        return
    
    # Run tests
    case_ok, case_value = test_case_detection(client)
    compare_ok, yearly_ok = test_scenario_compare(client)
    pdf_ok, pdf_size, pdf_hash, head_b64 = test_pdf_generation(client)
    
    print()
    print("=== VERIFICATION RESULTS ===")
    print(f"CASE DETECT: {'PASS' if case_ok else 'FAIL'} - case: {case_value}")
    print(f"COMPARE: {'PASS' if compare_ok else 'FAIL'} - yearly: {'available' if yearly_ok else 'unavailable'}")
    print(f"PDF: {'PASS' if pdf_ok else 'FAIL'} - size: {pdf_size} bytes")
    
    if pdf_ok:
        print(f"HEAD_B64: {head_b64}")
        print(f"PDF_SHA256: {pdf_hash}")
    
    # Create proof archive
    archive_path, archive_size = create_proof_archive()
    print(f"ARCHIVE: {archive_path} ({archive_size} bytes)")
    
    # Final verification hash
    all_passed = case_ok and compare_ok and pdf_ok and yearly_ok
    verification_data = f"{nonce}:{case_value}:{yearly_ok}:{pdf_hash}"
    verification_hash = hashlib.sha256(verification_data.encode()).hexdigest()
    
    print(f"VERIFICATION_HASH: {verification_hash}")
    print(f"STATUS: {'SUCCESS' if all_passed else 'PARTIAL'}")
    
    print("=== END SUMMARY ===")
    
    return all_passed

if __name__ == "__main__":
    main()
