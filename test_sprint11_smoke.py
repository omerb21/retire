#!/usr/bin/env python3
"""
Sprint11 Smoke Test Suite
Tests health, cashflow, compare, and PDF endpoints
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, Any

class Sprint11SmokeTest:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.results = {}
        self.artifacts_dir = "artifacts"
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
    def log_result(self, test_name: str, success: bool, details: Dict[str, Any]):
        """Log test result with details"""
        self.results[test_name] = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        print(f"{'✓' if success else '✗'} {test_name}: {'PASS' if success else 'FAIL'}")
        if not success and 'error' in details:
            print(f"  Error: {details['error']}")
    
    def test_health(self) -> bool:
        """Test API health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)
            success = response.status_code == 200 and response.json().get("status") == "ok"
            self.log_result("health", success, {
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            })
            return success
        except Exception as e:
            self.log_result("health", False, {"error": str(e)})
            return False
    
    def test_cashflow_generate(self, client_id: int = 1, scenario_id: int = 24) -> bool:
        """Test cashflow generation endpoint"""
        try:
            url = f"{self.base_url}/api/v1/scenarios/{scenario_id}/cashflow/generate"
            params = {"client_id": client_id}
            body = {
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
            
            response = requests.post(url, params=params, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                rows_count = len(data) if isinstance(data, list) else 0
                success = rows_count == 12
                
                # Save cashflow data
                with open(f"{self.artifacts_dir}/cashflow_live.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                self.log_result("cashflow_generate", success, {
                    "status_code": response.status_code,
                    "rows_count": rows_count,
                    "expected_rows": 12
                })
                return success
            else:
                self.log_result("cashflow_generate", False, {
                    "status_code": response.status_code,
                    "error": response.text
                })
                return False
                
        except Exception as e:
            self.log_result("cashflow_generate", False, {"error": str(e)})
            return False
    
    def test_compare_scenarios(self, client_id: int = 1, scenario_id: int = 24) -> bool:
        """Test scenarios compare endpoint"""
        try:
            url = f"{self.base_url}/api/v1/clients/{client_id}/scenarios/compare"
            body = {
                "scenarios": [scenario_id],
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
            
            response = requests.post(url, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                scenarios = data.get("scenarios", [])
                success = len(scenarios) == 1
                
                if success and scenarios:
                    monthly_count = len(scenarios[0].get("monthly", []))
                    yearly_totals = scenarios[0].get("yearly_totals", {})
                    success = monthly_count == 12 and "2025" in yearly_totals
                
                # Save compare data
                with open(f"{self.artifacts_dir}/compare_live.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                self.log_result("compare_scenarios", success, {
                    "status_code": response.status_code,
                    "scenarios_count": len(scenarios),
                    "monthly_count": monthly_count if 'monthly_count' in locals() else 0,
                    "has_yearly_2025": "2025" in yearly_totals if 'yearly_totals' in locals() else False
                })
                return success
            else:
                self.log_result("compare_scenarios", False, {
                    "status_code": response.status_code,
                    "error": response.text
                })
                return False
                
        except Exception as e:
            self.log_result("compare_scenarios", False, {"error": str(e)})
            return False
    
    def test_pdf_generation(self, client_id: int = 1, scenario_id: int = 24) -> bool:
        """Test PDF generation endpoint"""
        try:
            url = f"{self.base_url}/api/v1/scenarios/{scenario_id}/report/pdf"
            params = {"client_id": client_id}
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
            
            response = requests.post(url, params=params, json=body, timeout=60)
            
            if response.status_code == 200:
                pdf_content = response.content
                pdf_size = len(pdf_content)
                is_pdf = pdf_content.startswith(b'%PDF')
                success = pdf_size > 1024 and is_pdf
                
                # Save PDF file
                pdf_path = f"{self.artifacts_dir}/test.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(pdf_content)
                
                self.log_result("pdf_generation", success, {
                    "status_code": response.status_code,
                    "pdf_size": pdf_size,
                    "is_valid_pdf": is_pdf,
                    "pdf_path": pdf_path
                })
                return success
            else:
                # Save error response
                error_path = f"{self.artifacts_dir}/test.pdf.error"
                with open(error_path, "w") as f:
                    f.write(f"Status: {response.status_code}\n")
                    f.write(f"Error: {response.text}\n")
                
                self.log_result("pdf_generation", False, {
                    "status_code": response.status_code,
                    "error": response.text,
                    "error_file": error_path
                })
                return False
                
        except Exception as e:
            self.log_result("pdf_generation", False, {"error": str(e)})
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all smoke tests and return summary"""
        print("=== Sprint11 Smoke Test Suite ===")
        print(f"Testing API at: {self.base_url}")
        print()
        
        # Run tests in order
        health_ok = self.test_health()
        cashflow_ok = self.test_cashflow_generate() if health_ok else False
        compare_ok = self.test_compare_scenarios() if health_ok else False
        pdf_ok = self.test_pdf_generation() if health_ok else False
        
        # Calculate summary
        total_tests = 4
        passed_tests = sum([health_ok, cashflow_ok, compare_ok, pdf_ok])
        success_rate = passed_tests / total_tests
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": success_rate,
            "overall_success": success_rate == 1.0,
            "test_results": self.results
        }
        
        # Save summary
        with open(f"{self.artifacts_dir}/smoke_test_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print()
        print(f"=== Summary: {passed_tests}/{total_tests} tests passed ({success_rate:.1%}) ===")
        
        return summary

if __name__ == "__main__":
    tester = Sprint11SmokeTest()
    summary = tester.run_all_tests()
    
    if summary["overall_success"]:
        print("🎉 All smoke tests PASSED!")
        exit(0)
    else:
        print("❌ Some smoke tests FAILED!")
        exit(1)
