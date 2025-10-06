#!/usr/bin/env python3
"""
Sprint11 Complete Closure Script
Executes all closure checklist items and generates final artifacts
"""

import os
import json
import zipfile
import hashlib
import requests
import traceback
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

class Sprint11Closure:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8000"
        self.artifacts_dir = Path("artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = {}
        
    def log_result(self, step: str, status: str, details: dict = None):
        """Log step result"""
        self.results[step] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        print(f"{'✓' if status == 'PASS' else '✗'} {step}: {status}")
        if details:
            for key, value in details.items():
                print(f"  {key}: {value}")
    
    def test_health(self):
        """Test API health"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=10)
            if response.status_code == 200 and response.json().get("status") == "ok":
                self.log_result("health", "PASS", {"response": response.json()})
                return True
            else:
                self.log_result("health", "FAIL", {"status_code": response.status_code})
                return False
        except Exception as e:
            self.log_result("health", "FAIL", {"error": str(e)})
            return False
    
    def test_cashflow_generate(self):
        """Test cashflow generation with live data"""
        try:
            url = f"{self.base_url}/api/v1/scenarios/24/cashflow/generate"
            params = {"client_id": 1}
            body = {"from": "2025-01", "to": "2025-12", "frequency": "monthly"}
            
            response = requests.post(url, params=params, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                rows_count = len(data)
                
                # Save live cashflow data
                with open(self.artifacts_dir / "cashflow_live.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                if rows_count == 12:
                    self.log_result("cashflow_generate", "PASS", {
                        "rows_count": rows_count,
                        "date_range": f"{data[0]['date']}..{data[-1]['date']}"
                    })
                    return data
                else:
                    self.log_result("cashflow_generate", "FAIL", {
                        "expected_rows": 12,
                        "actual_rows": rows_count
                    })
                    return None
            else:
                self.log_result("cashflow_generate", "FAIL", {
                    "status_code": response.status_code,
                    "error": response.text
                })
                return None
                
        except Exception as e:
            self.log_result("cashflow_generate", "FAIL", {"error": str(e)})
            return None
    
    def test_compare_scenarios(self):
        """Test scenarios compare with live data"""
        try:
            url = f"{self.base_url}/api/v1/clients/1/scenarios/compare"
            body = {"scenarios": [24], "from": "2025-01", "to": "2025-12", "frequency": "monthly"}
            
            response = requests.post(url, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                scenarios = data.get("scenarios", [])
                
                # Save live compare data
                with open(self.artifacts_dir / "compare_live.json", "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                if scenarios and len(scenarios) == 1:
                    scenario = scenarios[0]
                    monthly_count = len(scenario.get("monthly", []))
                    yearly_totals = scenario.get("yearly_totals", {})
                    
                    if monthly_count == 12 and "2025" in yearly_totals:
                        self.log_result("compare_scenarios", "PASS", {
                            "scenario_count": len(scenarios),
                            "monthly_count": monthly_count,
                            "has_yearly_2025": True
                        })
                        return data
                    else:
                        self.log_result("compare_scenarios", "FAIL", {
                            "monthly_count": monthly_count,
                            "has_yearly_2025": "2025" in yearly_totals
                        })
                        return None
                else:
                    self.log_result("compare_scenarios", "FAIL", {
                        "scenarios_count": len(scenarios)
                    })
                    return None
            else:
                self.log_result("compare_scenarios", "FAIL", {
                    "status_code": response.status_code,
                    "error": response.text
                })
                return None
                
        except Exception as e:
            self.log_result("compare_scenarios", "FAIL", {"error": str(e)})
            return None
    
    def test_pdf_generation(self):
        """Test PDF generation with real output"""
        try:
            url = f"{self.base_url}/api/v1/scenarios/24/report/pdf"
            params = {"client_id": 1}
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
            
            # Save HTTP details
            with open(self.artifacts_dir / "report_pdf_run.log", "w") as f:
                f.write(f"HTTP Status: {response.status_code}\n")
                f.write(f"Headers: {dict(response.headers)}\n")
                f.write(f"Content-Length: {len(response.content)}\n")
                f.write(f"Content-Type: {response.headers.get('content-type', 'unknown')}\n")
            
            if response.status_code == 200:
                pdf_content = response.content
                pdf_size = len(pdf_content)
                is_valid_pdf = pdf_content.startswith(b'%PDF')
                
                if pdf_size > 1024 and is_valid_pdf:
                    # Save real PDF
                    with open(self.artifacts_dir / "test.pdf", "wb") as f:
                        f.write(pdf_content)
                    
                    self.log_result("pdf_generation", "PASS", {
                        "pdf_size": pdf_size,
                        "is_valid_pdf": is_valid_pdf,
                        "magic_header": pdf_content[:4].decode('latin-1')
                    })
                    return True
                else:
                    self.log_result("pdf_generation", "FAIL", {
                        "pdf_size": pdf_size,
                        "is_valid_pdf": is_valid_pdf,
                        "size_check": pdf_size > 1024
                    })
                    return False
            else:
                # Save error details
                with open(self.artifacts_dir / "test.pdf.error", "w") as f:
                    f.write(f"Status: {response.status_code}\n")
                    f.write(f"Error: {response.text}\n")
                
                self.log_result("pdf_generation", "FAIL", {
                    "status_code": response.status_code,
                    "error": response.text[:200]
                })
                return False
                
        except Exception as e:
            self.log_result("pdf_generation", "FAIL", {"error": str(e)})
            return False
    
    def verify_consistency(self, compare_data):
        """Verify monthly vs yearly totals consistency"""
        try:
            if not compare_data or not compare_data.get("scenarios"):
                self.log_result("consistency_check", "FAIL", {"error": "No compare data"})
                return False
            
            scenario = compare_data["scenarios"][0]
            monthly_data = scenario.get("monthly", [])
            yearly_data = scenario.get("yearly_totals", {}).get("2025", {})
            
            # Calculate monthly sums using Decimal precision
            monthly_sums = {
                "inflow": Decimal("0"),
                "outflow": Decimal("0"),
                "additional_income_net": Decimal("0"),
                "capital_return_net": Decimal("0"),
                "net": Decimal("0")
            }
            
            for month in monthly_data:
                for field in monthly_sums.keys():
                    value = Decimal(str(month.get(field, 0)))
                    monthly_sums[field] += value
            
            # Round to 2 decimal places
            for field in monthly_sums.keys():
                monthly_sums[field] = monthly_sums[field].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Compare with yearly totals
            consistency_results = {}
            all_consistent = True
            
            for field in monthly_sums.keys():
                monthly_val = float(monthly_sums[field])
                yearly_val = float(yearly_data.get(field, 0))
                diff = abs(monthly_val - yearly_val)
                
                is_consistent = diff <= 0.01
                consistency_results[field] = {
                    "monthly": monthly_val,
                    "yearly": yearly_val,
                    "diff": diff,
                    "consistent": is_consistent
                }
                
                if not is_consistent:
                    all_consistent = False
            
            # Save consistency check
            with open(self.artifacts_dir / "consistency_check.txt", "w") as f:
                f.write("Monthly vs Yearly Totals Consistency Check\n")
                f.write("=" * 50 + "\n\n")
                for field, result in consistency_results.items():
                    f.write(f"{field}:\n")
                    f.write(f"  Monthly sum: {result['monthly']}\n")
                    f.write(f"  Yearly total: {result['yearly']}\n")
                    f.write(f"  Difference: {result['diff']}\n")
                    f.write(f"  Consistent: {result['consistent']}\n\n")
                
                f.write(f"Overall consistency: {all_consistent}\n")
                f.write(f"Tolerance: ≤ 0.01\n")
            
            if all_consistent:
                self.log_result("consistency_check", "PASS", {
                    "net_monthly": consistency_results["net"]["monthly"],
                    "net_yearly": consistency_results["net"]["yearly"],
                    "net_diff": consistency_results["net"]["diff"]
                })
                return True
            else:
                self.log_result("consistency_check", "FAIL", consistency_results)
                return False
                
        except Exception as e:
            self.log_result("consistency_check", "FAIL", {"error": str(e)})
            return False
    
    def create_final_proof_zip(self):
        """Create final proof ZIP with SHA256"""
        try:
            zip_filename = f"yearly_totals_verification_{self.timestamp}.zip"
            zip_path = self.artifacts_dir / zip_filename
            
            # Files to include in proof
            proof_files = [
                "artifacts/cashflow_live.json",
                "artifacts/compare_live.json", 
                "artifacts/consistency_check.txt",
                "artifacts/report_pdf_run.log",
                "sprint11_integration_test.py",
                "test_pdf_fix.py",
                "app/services/report_service.py",
                "app/utils/contract_adapter.py"
            ]
            
            # Optional files
            optional_files = [
                "artifacts/test.pdf",
                "artifacts/test.pdf.error",
                "artifacts/sprint11_closure_log.txt"
            ]
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in proof_files:
                    if os.path.exists(file_path):
                        zipf.write(file_path, file_path)
                
                for file_path in optional_files:
                    if os.path.exists(file_path):
                        zipf.write(file_path, file_path)
            
            # Calculate SHA256
            sha256_hash = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            sha256_value = sha256_hash.hexdigest()
            zip_size = os.path.getsize(zip_path)
            
            # Save SHA256
            with open(self.artifacts_dir / "sha256.txt", "w") as f:
                f.write(f"{sha256_value}  {zip_filename}\n")
            
            self.log_result("create_proof_zip", "PASS", {
                "zip_filename": zip_filename,
                "zip_size": zip_size,
                "sha256": sha256_value[:16] + "..."
            })
            
            return {
                "zip_path": str(zip_path),
                "zip_size": zip_size,
                "sha256": sha256_value
            }
            
        except Exception as e:
            self.log_result("create_proof_zip", "FAIL", {"error": str(e)})
            return None
    
    def run_complete_closure(self):
        """Run complete Sprint11 closure checklist"""
        print("=" * 60)
        print("SPRINT11 COMPLETE CLOSURE EXECUTION")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print()
        
        # Step 1: Health check
        health_ok = self.test_health()
        if not health_ok:
            print("❌ Health check failed - cannot proceed")
            return self.generate_final_report(False)
        
        # Step 2: Cashflow generation
        cashflow_data = self.test_cashflow_generate()
        if not cashflow_data:
            print("❌ Cashflow generation failed")
            return self.generate_final_report(False)
        
        # Step 3: Compare scenarios
        compare_data = self.test_compare_scenarios()
        if not compare_data:
            print("❌ Compare scenarios failed")
            return self.generate_final_report(False)
        
        # Step 4: PDF generation
        pdf_ok = self.test_pdf_generation()
        
        # Step 5: Consistency check
        consistency_ok = self.verify_consistency(compare_data)
        if not consistency_ok:
            print("❌ Consistency check failed")
            return self.generate_final_report(False)
        
        # Step 6: Create proof ZIP
        proof_zip = self.create_final_proof_zip()
        if not proof_zip:
            print("❌ Proof ZIP creation failed")
            return self.generate_final_report(False)
        
        # Generate final report
        all_critical_passed = health_ok and cashflow_data and compare_data and consistency_ok and proof_zip
        return self.generate_final_report(all_critical_passed, proof_zip)
    
    def generate_final_report(self, success: bool, proof_zip: dict = None):
        """Generate final closure report"""
        
        # Mandatory closure criteria
        criteria = {
            "health_ok": self.results.get("health", {}).get("status") == "PASS",
            "compare_12_months": self.results.get("compare_scenarios", {}).get("details", {}).get("monthly_count") == 12,
            "consistency_check": self.results.get("consistency_check", {}).get("status") == "PASS",
            "pdf_real_generated": self.results.get("pdf_generation", {}).get("status") == "PASS",
            "proof_zip_created": self.results.get("create_proof_zip", {}).get("status") == "PASS"
        }
        
        all_criteria_met = all(criteria.values())
        
        final_report = {
            "sprint11_closure_status": {
                "timestamp": datetime.now().isoformat(),
                "overall_success": success and all_criteria_met,
                "branch": "sprint11-closure-20250908-164627",
                "commit_message": "Sprint11 closure: Fix PDF generation, normalize contracts, add Decimal precision"
            },
            "mandatory_criteria": criteria,
            "test_results": self.results,
            "artifacts_created": {
                "uvicorn_log": "artifacts/uvicorn.log" if os.path.exists("artifacts/uvicorn.log") else "NOT_FOUND",
                "compare_live_json": "artifacts/compare_live.json",
                "cashflow_live_json": "artifacts/cashflow_live.json", 
                "test_pdf": "artifacts/test.pdf" if os.path.exists("artifacts/test.pdf") else "artifacts/test.pdf.error",
                "consistency_check": "artifacts/consistency_check.txt",
                "report_pdf_log": "artifacts/report_pdf_run.log",
                "proof_zip": proof_zip["zip_path"] if proof_zip else "FAILED",
                "sha256": "artifacts/sha256.txt" if proof_zip else "FAILED"
            },
            "closure_verdict": "SUCCESS" if (success and all_criteria_met) else "FAILED",
            "next_steps": [
                "Create PR with changes",
                "Request QA/PO signoff", 
                "Merge to main branch",
                "Create release tag",
                "Update handoff documentation"
            ] if (success and all_criteria_met) else [
                "Review failed criteria",
                "Fix remaining issues",
                "Re-run closure checklist"
            ]
        }
        
        # Save final report
        with open(self.artifacts_dir / "sprint11_closure_final.json", "w") as f:
            json.dump(final_report, f, indent=2)
        
        print("\n" + "=" * 60)
        print("SPRINT11 CLOSURE FINAL REPORT")
        print("=" * 60)
        print(f"Overall Success: {final_report['overall_success']}")
        print(f"Closure Verdict: {final_report['closure_verdict']}")
        print()
        print("Mandatory Criteria:")
        for criterion, status in criteria.items():
            print(f"  {'✓' if status else '✗'} {criterion}: {status}")
        
        if proof_zip:
            print(f"\nProof ZIP: {proof_zip['zip_path']}")
            print(f"SHA256: {proof_zip['sha256']}")
        
        return final_report

if __name__ == "__main__":
    closure = Sprint11Closure()
    result = closure.run_complete_closure()
    
    if result["overall_success"]:
        print("\n🎉 Sprint11 closure COMPLETED successfully!")
        exit(0)
    else:
        print("\n❌ Sprint11 closure FAILED - check report for details")
        exit(1)
