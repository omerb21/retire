#!/usr/bin/env python3
"""
Sprint11 Direct API Test - Manual execution of smoke tests
"""

import requests
import json
import os
from datetime import datetime

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=10)
        print(f"Health: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health failed: {e}")
        return False

def test_compare():
    """Test compare endpoint"""
    try:
        url = "http://127.0.0.1:8000/api/v1/clients/1/scenarios/compare"
        body = {
            "scenarios": [24],
            "from": "2025-01",
            "to": "2025-12",
            "frequency": "monthly"
        }
        response = requests.post(url, json=body, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            scenarios = data.get("scenarios", [])
            if scenarios:
                monthly_count = len(scenarios[0].get("monthly", []))
                yearly = scenarios[0].get("yearly_totals", {})
                print(f"Compare: {response.status_code} - {len(scenarios)} scenarios, {monthly_count} months, yearly: {list(yearly.keys())}")
                
                # Save data
                os.makedirs("artifacts", exist_ok=True)
                with open("artifacts/compare_live.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                return monthly_count == 12
            else:
                print(f"Compare: {response.status_code} - No scenarios returned")
                return False
        else:
            print(f"Compare failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Compare failed: {e}")
        return False

def test_pdf():
    """Test PDF endpoint"""
    try:
        url = "http://127.0.0.1:8000/api/v1/scenarios/24/report/pdf?client_id=1"
        body = {
            "from": "2025-01",
            "to": "2025-12",
            "frequency": "monthly",
            "sections": {
                "summary": True,
                "cashflow_table": True,
                "net_chart": True,
                "scenarios_compare": True
            }
        }
        response = requests.post(url, json=body, timeout=60)
        
        if response.status_code == 200:
            pdf_content = response.content
            pdf_size = len(pdf_content)
            is_pdf = pdf_content.startswith(b'%PDF')
            
            os.makedirs("artifacts", exist_ok=True)
            with open("artifacts/test.pdf", "wb") as f:
                f.write(pdf_content)
            
            print(f"PDF: {response.status_code} - {pdf_size} bytes, valid PDF: {is_pdf}")
            return pdf_size > 1024 and is_pdf
        else:
            print(f"PDF failed: {response.status_code} - {response.text}")
            with open("artifacts/test.pdf.error", "w") as f:
                f.write(f"Status: {response.status_code}\nError: {response.text}")
            return False
    except Exception as e:
        print(f"PDF failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Sprint11 Direct API Test ===")
    
    health_ok = test_health()
    compare_ok = test_compare() if health_ok else False
    pdf_ok = test_pdf() if health_ok else False
    
    passed = sum([health_ok, compare_ok, pdf_ok])
    total = 3
    
    print(f"\n=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests PASSED!")
    else:
        print("❌ Some tests FAILED!")
