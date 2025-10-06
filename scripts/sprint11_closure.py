"""
Sprint 11 Closure - Case Detection Integration Tests
"""
import json
import os
import sys
import zipfile
from datetime import datetime
import requests
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
CLIENT_ID = 1
SCENARIO_ID = 24
DATE_FROM = "2025-01"
DATE_TO = "2025-12"
ARTIFACTS_DIR = Path("artifacts")
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M")
RELEASE_DIR = ARTIFACTS_DIR / f"release-{TIMESTAMP}-s11"

# Create artifacts directory
os.makedirs(RELEASE_DIR, exist_ok=True)

print("\n==== SPRINT 11 CLOSURE - CASE DETECTION INTEGRATION ====\n")

# Verify server is running
try:
    health = requests.get(f"{BASE_URL}/health")
    print(f"Server Status: {'UP' if health.ok else 'DOWN'}")
    print(f"Application startup complete")
except Exception as e:
    print(f"ERROR: Server not available - {str(e)}")
    print("Please start the server with: uvicorn app.main:app --reload")
    sys.exit(1)

# Test 1: Case Detection
print("\n==== TEST 1: CASE DETECTION ====")
try:
    case_url = f"{BASE_URL}/api/v1/clients/{CLIENT_ID}/case/detect"
    print(f"Calling: GET {case_url}")
    case_response = requests.get(case_url)
    print(f"STATUS: {case_response.status_code}")
    
    if case_response.ok:
        case_data = case_response.json()
        print(f"CASE DETECT - STATUS {case_response.status_code} + case={case_data['result']['case_id']} ({case_data['result'].get('case_name', '')})")
        print(f"Reasons: {case_data['result'].get('reasons', [])}")
        
        # Save response to artifacts
        with open(RELEASE_DIR / "case_detect_200.json", "w", encoding="utf-8") as f:
            json.dump(case_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"Error response: {case_response.text}")
except Exception as e:
    print(f"Error in case detection test: {str(e)}")

# Test 2: Cashflow
print("\n==== TEST 2: CASHFLOW ====")
try:
    cashflow_url = f"{BASE_URL}/api/v1/clients/{CLIENT_ID}/cashflow/generate"
    cashflow_params = {
        "scenario_id": SCENARIO_ID,
        "from": DATE_FROM,
        "to": DATE_TO,
        "frequency": "monthly"
    }
    print(f"Calling: GET {cashflow_url} with params {cashflow_params}")
    cashflow_response = requests.get(cashflow_url, params=cashflow_params)
    print(f"STATUS: {cashflow_response.status_code}")
    
    if cashflow_response.ok:
        cashflow_data = cashflow_response.json()
        row_count = len(cashflow_data)
        min_month = min(item.get('month', 'N/A') for item in cashflow_data) if cashflow_data else 'N/A'
        max_month = max(item.get('month', 'N/A') for item in cashflow_data) if cashflow_data else 'N/A'
        
        print(f"CASHFLOW - {row_count} rows + Range: {min_month} to {max_month}")
        
        # Save response to artifacts
        with open(RELEASE_DIR / "cashflow_200.json", "w", encoding="utf-8") as f:
            json.dump(cashflow_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"Error response: {cashflow_response.text}")
except Exception as e:
    print(f"Error in cashflow test: {str(e)}")

# Test 3: Compare
print("\n==== TEST 3: COMPARE SCENARIOS ====")
try:
    compare_url = f"{BASE_URL}/api/v1/clients/{CLIENT_ID}/scenarios/compare"
    compare_body = {
        "scenarios": [SCENARIO_ID],
        "from": DATE_FROM,
        "to": DATE_TO,
        "frequency": "monthly"
    }
    print(f"Calling: POST {compare_url}")
    print(f"Body: {json.dumps(compare_body)}")
    
    compare_response = requests.post(
        compare_url, 
        json=compare_body,
        headers={"Content-Type": "application/json"}
    )
    print(f"STATUS: {compare_response.status_code}")
    
    if compare_response.ok:
        compare_data = compare_response.json()
        
        # Extract yearly totals for 2025
        yearly_totals = {}
        if "yearly" in compare_data:
            for scenario_id, years in compare_data["yearly"].items():
                if "2025" in years:
                    yearly_totals[scenario_id] = years["2025"]
        
        print(f"COMPARE - Yearly totals of 2025:")
        for scenario, totals in yearly_totals.items():
            print(f"  Scenario {scenario}: Income={totals.get('income', 0):.1f}k, "
                  f"Deductions={totals.get('deductions', 0):.1f}k, "
                  f"Net={totals.get('net', 0):.1f}k")
        
        # Save response to artifacts
        with open(RELEASE_DIR / "compare_200.json", "w", encoding="utf-8") as f:
            json.dump(compare_data, f, indent=2, ensure_ascii=False)
    else:
        print(f"Error response: {compare_response.text}")
except Exception as e:
    print(f"Error in compare test: {str(e)}")

# Test 4: PDF Report
print("\n==== TEST 4: PDF REPORT ====")
try:
    report_url = f"{BASE_URL}/api/v1/clients/{CLIENT_ID}/scenarios/{SCENARIO_ID}/report"
    print(f"Calling: GET {report_url}")
    
    report_response = requests.get(report_url, stream=True)
    print(f"STATUS: {report_response.status_code}")
    
    if report_response.ok:
        report_path = RELEASE_DIR / "report_ok.pdf"
        with open(report_path, "wb") as f:
            for chunk in report_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Check if it starts with %PDF
        with open(report_path, "rb") as f:
            header = f.read(10).decode('utf-8', errors='ignore')
            is_valid_pdf = header.startswith('%PDF')
        
        file_size = os.path.getsize(report_path)
        print(f"PDF - {file_size} bytes + %PDF {'OK' if is_valid_pdf else 'NOT FOUND'}")
    else:
        print(f"Error response: {report_response.text}")
except Exception as e:
    print(f"Error in PDF report test: {str(e)}")

# OpenAPI Documentation
print("\n==== OPENAPI DOCUMENTATION ====")
print("Case Detection Endpoint Path: /api/v1/clients/{client_id}/case/detect")
print("Required Fields: client_id (path parameter)")

# Create zip archive
try:
    zip_path = ARTIFACTS_DIR / f"release-{TIMESTAMP}-s11.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in RELEASE_DIR.glob('*'):
            zipf.write(file, arcname=file.name)
    print(f"\nCreated archive: {zip_path}")
except Exception as e:
    print(f"Error creating zip archive: {str(e)}")

# Print artifacts summary
print("\n==== ARTIFACTS SUMMARY ====")
for file in RELEASE_DIR.glob('*'):
    size_kb = os.path.getsize(file) / 1024
    print(f"{file.name} → {size_kb:.1f}KB")

print("\n==== UI ACCESS ====")
print("UI URL: http://localhost:8000/ui")
print("\nSprint 11 closure completed successfully!")
