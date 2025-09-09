#!/usr/bin/env python3
"""
Sprint11 Canonical Run - Single authoritative execution
Creates definitive artifacts from one continuous run
"""

import os
import json
import zipfile
import hashlib
import requests
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

class Sprint11CanonicalRun:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8000"
        self.artifacts_dir = Path("artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.commit_sha = "sprint11-closure-20250908-164627"  # Our branch
        
    def run_canonical_sequence(self):
        """Execute single authoritative run: cashflow → compare → PDF"""
        print("=" * 60)
        print("SPRINT11 CANONICAL RUN - DEFINITIVE EXECUTION")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"Commit: {self.commit_sha}")
        print(f"Base URL: {self.base_url}")
        print()
        
        results = {
            "run_info": {
                "timestamp": self.timestamp,
                "commit_sha": self.commit_sha,
                "base_url": self.base_url
            },
            "steps": {}
        }
        
        # Step 1: Generate Cashflow (live data)
        print("1. Generating cashflow (live API)...")
        cashflow_data = self.generate_cashflow_live()
        if not cashflow_data:
            print("❌ Cashflow generation failed - aborting")
            return None
        results["steps"]["cashflow"] = {"status": "PASS", "rows": len(cashflow_data)}
        
        # Step 2: Compare Scenarios (live data)
        print("2. Running compare scenarios (live API)...")
        compare_data = self.compare_scenarios_live()
        if not compare_data:
            print("❌ Compare scenarios failed - aborting")
            return None
        results["steps"]["compare"] = {"status": "PASS", "scenarios": len(compare_data.get("scenarios", []))}
        
        # Step 3: Generate PDF (real PDF)
        print("3. Generating PDF report (real PDF)...")
        pdf_result = self.generate_pdf_live()
        results["steps"]["pdf"] = pdf_result
        
        # Step 4: Consistency Check
        print("4. Running consistency check...")
        consistency_result = self.check_consistency(compare_data)
        results["steps"]["consistency"] = consistency_result
        
        if not consistency_result["passed"]:
            print("❌ Consistency check failed - aborting")
            return None
        
        # Step 5: Create ZIP with SHA256
        print("5. Creating proof ZIP...")
        zip_result = self.create_proof_zip()
        results["steps"]["zip"] = zip_result
        
        # Save run results
        with open(self.artifacts_dir / f"canonical_run_{self.timestamp}.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print("\n" + "=" * 60)
        print("✅ CANONICAL RUN COMPLETED")
        print("=" * 60)
        print(f"Artifacts saved with timestamp: {self.timestamp}")
        print(f"ZIP: {zip_result['zip_filename'] if zip_result else 'FAILED'}")
        print(f"SHA256: {zip_result['sha256'][:16] + '...' if zip_result else 'FAILED'}")
        
        return results
    
    def generate_cashflow_live(self):
        """Generate cashflow from live API"""
        try:
            url = f"{self.base_url}/api/v1/scenarios/24/cashflow/generate"
            params = {"client_id": 1}
            body = {"from": "2025-01", "to": "2025-12", "frequency": "monthly"}
            
            response = requests.post(url, params=params, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Save with timestamp
                filename = f"cashflow_live_{self.timestamp}.json"
                with open(self.artifacts_dir / filename, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                print(f"   ✓ Saved: {filename} ({len(data)} rows)")
                return data
            else:
                print(f"   ✗ Failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"   ✗ Exception: {e}")
            return None
    
    def compare_scenarios_live(self):
        """Compare scenarios from live API"""
        try:
            url = f"{self.base_url}/api/v1/clients/1/scenarios/compare"
            body = {"scenarios": [24], "from": "2025-01", "to": "2025-12", "frequency": "monthly"}
            
            response = requests.post(url, json=body, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Save with timestamp
                filename = f"compare_live_{self.timestamp}.json"
                with open(self.artifacts_dir / filename, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                scenarios = data.get("scenarios", [])
                monthly_count = len(scenarios[0].get("monthly", [])) if scenarios else 0
                print(f"   ✓ Saved: {filename} ({len(scenarios)} scenarios, {monthly_count} months)")
                return data
            else:
                print(f"   ✗ Failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"   ✗ Exception: {e}")
            return None
    
    def generate_pdf_live(self):
        """Generate PDF from live API"""
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
            
            # Save HTTP log
            log_filename = f"pdf_run_{self.timestamp}.log"
            with open(self.artifacts_dir / log_filename, "w") as f:
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
                    pdf_filename = f"test_{self.timestamp}.pdf"
                    with open(self.artifacts_dir / pdf_filename, "wb") as f:
                        f.write(pdf_content)
                    
                    print(f"   ✓ Saved: {pdf_filename} ({pdf_size} bytes, valid PDF)")
                    return {"status": "PASS", "filename": pdf_filename, "size": pdf_size, "valid": True}
                else:
                    print(f"   ✗ Invalid PDF: size={pdf_size}, valid={is_valid_pdf}")
                    return {"status": "FAIL", "size": pdf_size, "valid": is_valid_pdf}
            else:
                # Save error
                error_filename = f"pdf_error_{self.timestamp}.txt"
                with open(self.artifacts_dir / error_filename, "w") as f:
                    f.write(f"Status: {response.status_code}\n")
                    f.write(f"Error: {response.text}\n")
                
                print(f"   ✗ Failed: {response.status_code} - saved to {error_filename}")
                return {"status": "FAIL", "error_file": error_filename}
                
        except Exception as e:
            print(f"   ✗ Exception: {e}")
            return {"status": "FAIL", "error": str(e)}
    
    def check_consistency(self, compare_data):
        """Check monthly vs yearly consistency"""
        try:
            if not compare_data or not compare_data.get("scenarios"):
                return {"passed": False, "error": "No compare data"}
            
            scenario = compare_data["scenarios"][0]
            monthly_data = scenario.get("monthly", [])
            yearly_data = scenario.get("yearly_totals", {}).get("2025", {})
            
            # Calculate monthly sum with Decimal precision
            monthly_sum_net = Decimal("0")
            for month in monthly_data:
                net_val = Decimal(str(month.get("net", 0)))
                monthly_sum_net += net_val
            
            # Round to 2 decimal places
            monthly_sum_net = monthly_sum_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            yearly_net = Decimal(str(yearly_data.get("net", 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            diff = abs(monthly_sum_net - yearly_net)
            passed = diff <= Decimal("0.01")
            
            # Save consistency check
            check_filename = f"consistency_check_{self.timestamp}.txt"
            with open(self.artifacts_dir / check_filename, "w") as f:
                f.write("Monthly vs Yearly Totals Consistency Check\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Monthly sum (net): {monthly_sum_net}\n")
                f.write(f"Yearly total (net): {yearly_net}\n")
                f.write(f"Difference: {diff}\n")
                f.write(f"Tolerance: ≤ 0.01\n")
                f.write(f"Result: {'PASS' if passed else 'FAIL'}\n")
                f.write(f"Timestamp: {self.timestamp}\n")
                f.write(f"Commit: {self.commit_sha}\n")
            
            print(f"   {'✓' if passed else '✗'} Monthly={monthly_sum_net}, Yearly={yearly_net}, Diff={diff}")
            print(f"   Saved: {check_filename}")
            
            return {
                "passed": passed,
                "monthly_net": float(monthly_sum_net),
                "yearly_net": float(yearly_net),
                "diff": float(diff),
                "filename": check_filename
            }
            
        except Exception as e:
            print(f"   ✗ Exception: {e}")
            return {"passed": False, "error": str(e)}
    
    def create_proof_zip(self):
        """Create proof ZIP with SHA256"""
        try:
            zip_filename = f"yearly_totals_verification_{self.timestamp}.zip"
            zip_path = self.artifacts_dir / zip_filename
            
            # Files to include (with timestamp)
            files_to_zip = [
                f"cashflow_live_{self.timestamp}.json",
                f"compare_live_{self.timestamp}.json",
                f"consistency_check_{self.timestamp}.txt",
                f"pdf_run_{self.timestamp}.log",
                f"canonical_run_{self.timestamp}.json"
            ]
            
            # Optional files
            optional_files = [
                f"test_{self.timestamp}.pdf",
                f"pdf_error_{self.timestamp}.txt"
            ]
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in files_to_zip:
                    file_path = self.artifacts_dir / filename
                    if file_path.exists():
                        zipf.write(file_path, f"artifacts/{filename}")
                
                for filename in optional_files:
                    file_path = self.artifacts_dir / filename
                    if file_path.exists():
                        zipf.write(file_path, f"artifacts/{filename}")
            
            # Calculate SHA256
            sha256_hash = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            sha256_value = sha256_hash.hexdigest()
            zip_size = os.path.getsize(zip_path)
            
            # Save SHA256
            sha256_filename = f"zip_sha256_{self.timestamp}.txt"
            with open(self.artifacts_dir / sha256_filename, "w") as f:
                f.write(f"{sha256_value}  {zip_filename}\n")
                f.write(f"Size: {zip_size} bytes\n")
                f.write(f"Created: {datetime.now().isoformat()}\n")
                f.write(f"Commit: {self.commit_sha}\n")
            
            print(f"   ✓ Created: {zip_filename} ({zip_size} bytes)")
            print(f"   ✓ SHA256: {sha256_value[:16]}...")
            print(f"   ✓ Saved: {sha256_filename}")
            
            return {
                "zip_filename": zip_filename,
                "zip_size": zip_size,
                "sha256": sha256_value,
                "sha256_file": sha256_filename
            }
            
        except Exception as e:
            print(f"   ✗ Exception: {e}")
            return None

if __name__ == "__main__":
    runner = Sprint11CanonicalRun()
    result = runner.run_canonical_sequence()
    
    if result and all(step.get("status") != "FAIL" for step in result["steps"].values() if isinstance(step, dict)):
        print("\n🎉 CANONICAL RUN SUCCESS - Ready for QA signoff!")
        exit(0)
    else:
        print("\n❌ CANONICAL RUN FAILED - Check errors above")
        exit(1)
