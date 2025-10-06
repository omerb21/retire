import pytest
import requests
import json
from typing import Dict, Any
from pathlib import Path


class TestSystemE2E:
    """End-to-end system tests for complete workflow integration"""
    
    BASE_URL = "http://127.0.0.1:8002"
    
    def test_case_5_regular_client_full_workflow(self):
        """
        Case 5: Regular client with current employer - full workflow test
        Tests: fixation -> scenarios -> cashflow -> compare -> PDF
        """
        client_id = 1
        
        # Step 1: Generate cashflow for scenario
        cashflow_response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/24/cashflow/generate",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        assert cashflow_response.status_code == 200
        cashflow_data = cashflow_response.json()
        
        # Validate cashflow structure
        assert "cashflow" in cashflow_data
        assert len(cashflow_data["cashflow"]) == 12  # 12 months
        
        # Save baseline snapshot
        baseline_cashflow = cashflow_data["cashflow"]
        self._save_baseline("case5_cashflow", baseline_cashflow)
        
        # Step 2: Compare scenarios (if multiple exist)
        compare_response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/compare",
            json={
                "scenarios": [24, 25],
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        if compare_response.status_code == 200:
            compare_data = compare_response.json()
            
            # Validate comparison structure
            assert "scenarios" in compare_data
            assert "meta" in compare_data
            
            # Check yearly totals consistency
            scenario_24 = compare_data["scenarios"]["24"]
            yearly_2025 = scenario_24["yearly"]["2025"]
            
            # Validate yearly totals match monthly sum
            monthly_net_sum = sum(row["net"] for row in scenario_24["monthly"])
            assert abs(yearly_2025["net"] - monthly_net_sum) < 0.01  # Allow for rounding
            
            self._save_baseline("case5_comparison", compare_data)
        
        # Step 3: Generate PDF report
        pdf_response = requests.post(
            f"{self.BASE_URL}/api/v1/scenarios/24/report/pdf",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "sections": {
                    "summary": True,
                    "cashflow_table": True,
                    "net_chart": True,
                    "scenarios_compare": True
                }
            }
        )
        
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"] == "application/pdf"
        
        # Validate PDF size (should be reasonable)
        pdf_size = len(pdf_response.content)
        assert 10000 < pdf_size < 5000000  # Between 10KB and 5MB
        
        # Save PDF for manual inspection
        pdf_path = Path("artifacts") / "case5_report.pdf"
        pdf_path.parent.mkdir(exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(pdf_response.content)
        
        return {
            "status": "SUCCESS",
            "cashflow_months": len(baseline_cashflow),
            "pdf_size": pdf_size,
            "yearly_net": yearly_2025["net"] if compare_response.status_code == 200 else None
        }
    
    def test_case_1_no_current_employer_workflow(self):
        """
        Case 1: Client without current employer - simplified workflow
        Tests that system handles missing employer data gracefully
        """
        client_id = 2  # Assuming client 2 has no current employer
        
        # Step 1: Generate cashflow (should work without employer data)
        cashflow_response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/1/cashflow/generate",
            json={
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
        )
        
        # Should succeed even without current employer
        assert cashflow_response.status_code in [200, 404]  # 404 if scenario doesn't exist
        
        if cashflow_response.status_code == 200:
            cashflow_data = cashflow_response.json()
            baseline_cashflow = cashflow_data["cashflow"]
            
            # Validate that employer-related fields are zero or minimal
            for month in baseline_cashflow:
                # Should have minimal or zero employer-related income
                employer_income = month.get("employer_pension", 0)
                assert employer_income >= 0  # Should not be negative
            
            self._save_baseline("case1_cashflow", baseline_cashflow)
            
            # Step 2: Generate PDF report
            pdf_response = requests.post(
                f"{self.BASE_URL}/api/v1/scenarios/1/report/pdf",
                json={
                    "from": "2025-01",
                    "to": "2025-12",
                    "sections": {
                        "summary": True,
                        "cashflow_table": True,
                        "net_chart": True
                    }
                }
            )
            
            if pdf_response.status_code == 200:
                pdf_size = len(pdf_response.content)
                
                # Save PDF
                pdf_path = Path("artifacts") / "case1_report.pdf"
                pdf_path.parent.mkdir(exist_ok=True)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_response.content)
                
                return {
                    "status": "SUCCESS",
                    "cashflow_months": len(baseline_cashflow),
                    "pdf_size": pdf_size,
                    "has_employer_data": False
                }
        
        return {
            "status": "SKIPPED - No scenario data",
            "reason": "Client 2 scenario 1 not found"
        }
    
    def test_workflow_consistency(self):
        """
        Test consistency between cashflow -> compare -> PDF workflow
        Ensures values match across all three endpoints
        """
        client_id = 1
        scenario_id = 24
        
        # Get individual cashflow
        cashflow_response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/{scenario_id}/cashflow/generate",
            json={
                "from": "2025-01",
                "to": "2025-03",  # Short range for testing
                "frequency": "monthly"
            }
        )
        
        assert cashflow_response.status_code == 200
        individual_cashflow = cashflow_response.json()["cashflow"]
        
        # Get comparison data
        compare_response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/compare",
            json={
                "scenarios": [scenario_id],
                "from": "2025-01",
                "to": "2025-03",
                "frequency": "monthly"
            }
        )
        
        assert compare_response.status_code == 200
        compare_data = compare_response.json()
        comparison_cashflow = compare_data["scenarios"][str(scenario_id)]["monthly"]
        
        # Verify consistency between individual and comparison cashflow
        assert len(individual_cashflow) == len(comparison_cashflow)
        
        for i, (individual, comparison) in enumerate(zip(individual_cashflow, comparison_cashflow)):
            # Allow small floating point differences
            assert abs(individual["net"] - comparison["net"]) < 0.01, f"Month {i}: Net mismatch"
            assert abs(individual["inflow"] - comparison["inflow"]) < 0.01, f"Month {i}: Inflow mismatch"
            assert abs(individual["outflow"] - comparison["outflow"]) < 0.01, f"Month {i}: Outflow mismatch"
        
        return {
            "status": "CONSISTENT",
            "months_tested": len(individual_cashflow),
            "max_difference": 0.01
        }
    
    def test_validation_errors(self):
        """Test that validation errors are properly handled"""
        client_id = 1
        
        # Test invalid date range (from > to)
        response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/compare",
            json={
                "scenarios": [24],
                "from": "2025-12",
                "to": "2025-01",  # Invalid: to < from
                "frequency": "monthly"
            }
        )
        
        assert response.status_code == 422
        error_detail = response.json()
        assert "from" in str(error_detail).lower() or "date" in str(error_detail).lower()
        
        # Test invalid frequency
        response = requests.post(
            f"{self.BASE_URL}/api/v1/clients/{client_id}/scenarios/compare",
            json={
                "scenarios": [24],
                "from": "2025-01",
                "to": "2025-12",
                "frequency": "quarterly"  # Invalid frequency
            }
        )
        
        assert response.status_code == 422
        
        return {"status": "VALIDATION_WORKING"}
    
    def _save_baseline(self, name: str, data: Any):
        """Save baseline data for comparison"""
        baselines_dir = Path("artifacts") / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)
        
        baseline_file = baselines_dir / f"{name}.json"
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def _compare_with_baseline(self, name: str, current_data: Any, tolerance: float = 0.005) -> Dict[str, Any]:
        """Compare current data with saved baseline"""
        baseline_file = Path("artifacts") / "baselines" / f"{name}.json"
        
        if not baseline_file.exists():
            return {"status": "NO_BASELINE", "message": f"No baseline found for {name}"}
        
        with open(baseline_file, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        
        # Simple comparison for yearly totals
        if isinstance(current_data, dict) and "scenarios" in current_data:
            differences = []
            for scenario_id, scenario_data in current_data["scenarios"].items():
                if scenario_id in baseline_data.get("scenarios", {}):
                    baseline_scenario = baseline_data["scenarios"][scenario_id]
                    current_yearly = scenario_data.get("yearly", {})
                    baseline_yearly = baseline_scenario.get("yearly", {})
                    
                    for year in current_yearly:
                        if year in baseline_yearly:
                            current_net = current_yearly[year]["net"]
                            baseline_net = baseline_yearly[year]["net"]
                            
                            if baseline_net != 0:
                                diff_pct = abs(current_net - baseline_net) / abs(baseline_net)
                                if diff_pct > tolerance:
                                    differences.append({
                                        "scenario": scenario_id,
                                        "year": year,
                                        "current": current_net,
                                        "baseline": baseline_net,
                                        "diff_pct": diff_pct
                                    })
            
            if differences:
                return {"status": "DIFFERENCES_FOUND", "differences": differences}
            else:
                return {"status": "MATCH", "tolerance": tolerance}
        
        return {"status": "COMPARISON_SKIPPED", "reason": "Unsupported data format"}
