#!/usr/bin/env python3
"""
Load testing script for Sprint 10
Performs 100 graduated API calls to test system performance
"""

import requests
import time
import statistics
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import json


class LoadTester:
    def __init__(self, base_url: str = "http://127.0.0.1:8002"):
        self.base_url = base_url
        self.results = []
    
    def test_cashflow_generate(self, client_id: int = 1, scenario_id: int = 24) -> Dict[str, Any]:
        """Test cashflow generation endpoint"""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/clients/{client_id}/scenarios/{scenario_id}/cashflow/generate",
                json={
                    "from": "2025-01",
                    "to": "2025-12",
                    "frequency": "monthly"
                },
                timeout=5.0
            )
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000  # Convert to ms
            
            return {
                "endpoint": "cashflow_generate",
                "status_code": response.status_code,
                "duration_ms": duration,
                "success": response.status_code == 200,
                "response_size": len(response.content) if response.content else 0
            }
        
        except Exception as e:
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "endpoint": "cashflow_generate",
                "status_code": 0,
                "duration_ms": duration,
                "success": False,
                "error": str(e)
            }
    
    def test_scenario_compare(self, client_id: int = 1, scenarios: List[int] = [24, 25]) -> Dict[str, Any]:
        """Test scenario comparison endpoint"""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/clients/{client_id}/scenarios/compare",
                json={
                    "scenarios": scenarios,
                    "from": "2025-01",
                    "to": "2025-12",
                    "frequency": "monthly"
                },
                timeout=10.0
            )
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "endpoint": "scenario_compare",
                "status_code": response.status_code,
                "duration_ms": duration,
                "success": response.status_code == 200,
                "response_size": len(response.content) if response.content else 0
            }
        
        except Exception as e:
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "endpoint": "scenario_compare",
                "status_code": 0,
                "duration_ms": duration,
                "success": False,
                "error": str(e)
            }
    
    def test_pdf_generate(self, scenario_id: int = 24) -> Dict[str, Any]:
        """Test PDF generation endpoint"""
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/scenarios/{scenario_id}/report/pdf",
                json={
                    "from": "2025-01",
                    "to": "2025-12",
                    "sections": {
                        "summary": True,
                        "cashflow_table": True,
                        "net_chart": True,
                        "scenarios_compare": True
                    }
                },
                timeout=15.0
            )
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "endpoint": "pdf_generate",
                "status_code": response.status_code,
                "duration_ms": duration,
                "success": response.status_code == 200,
                "response_size": len(response.content) if response.content else 0
            }
        
        except Exception as e:
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "endpoint": "pdf_generate",
                "status_code": 0,
                "duration_ms": duration,
                "success": False,
                "error": str(e)
            }
    
    def run_load_test(self):
        """Run the complete load test suite"""
        print("Starting load test...")
        print(f"Target: {self.base_url}")
        print("=" * 50)
        
        # Test server availability first
        try:
            health_response = requests.get(f"{self.base_url}/", timeout=5.0)
            if health_response.status_code != 200:
                print(f"❌ Server not responding properly: {health_response.status_code}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return
        
        print("✅ Server is responding")
        
        # Run tests sequentially (not parallel to avoid overwhelming the system)
        
        # 50× cashflow generation
        print("\n📊 Testing cashflow generation (50 calls)...")
        cashflow_results = []
        for i in range(50):
            if i % 10 == 0:
                print(f"  Progress: {i}/50")
            
            result = self.test_cashflow_generate()
            cashflow_results.append(result)
            self.results.append(result)
            
            # Small delay to avoid overwhelming
            time.sleep(0.1)
        
        # 30× scenario comparison
        print("\n🔄 Testing scenario comparison (30 calls)...")
        compare_results = []
        for i in range(30):
            if i % 10 == 0:
                print(f"  Progress: {i}/30")
            
            result = self.test_scenario_compare()
            compare_results.append(result)
            self.results.append(result)
            
            time.sleep(0.1)
        
        # 20× PDF generation
        print("\n📄 Testing PDF generation (20 calls)...")
        pdf_results = []
        for i in range(20):
            if i % 5 == 0:
                print(f"  Progress: {i}/20")
            
            result = self.test_pdf_generate()
            pdf_results.append(result)
            self.results.append(result)
            
            time.sleep(0.2)  # Longer delay for PDF generation
        
        # Analyze results
        self.analyze_results(cashflow_results, compare_results, pdf_results)
    
    def analyze_results(self, cashflow_results: List[Dict], compare_results: List[Dict], pdf_results: List[Dict]):
        """Analyze and report test results"""
        print("\n" + "=" * 50)
        print("📈 LOAD TEST RESULTS")
        print("=" * 50)
        
        # Overall success rate
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r["success"])
        success_rate = (successful_tests / total_tests) * 100
        
        print(f"Overall Success Rate: {success_rate:.1f}% ({successful_tests}/{total_tests})")
        
        if success_rate < 100:
            print("❌ FAILED: Not all tests passed")
            failed_tests = [r for r in self.results if not r["success"]]
            for failed in failed_tests[:5]:  # Show first 5 failures
                print(f"  - {failed['endpoint']}: {failed.get('error', 'HTTP ' + str(failed['status_code']))}")
        else:
            print("✅ SUCCESS: All tests passed")
        
        # Performance analysis by endpoint
        endpoints = {
            "cashflow_generate": cashflow_results,
            "scenario_compare": compare_results,
            "pdf_generate": pdf_results
        }
        
        print(f"\n{'Endpoint':<20} {'Count':<8} {'Avg(ms)':<10} {'Median(ms)':<12} {'95th(ms)':<10} {'Status'}")
        print("-" * 70)
        
        for endpoint_name, results in endpoints.items():
            if not results:
                continue
                
            successful_results = [r for r in results if r["success"]]
            
            if successful_results:
                durations = [r["duration_ms"] for r in successful_results]
                avg_duration = statistics.mean(durations)
                median_duration = statistics.median(durations)
                p95_duration = durations[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0]
                
                # Check performance criteria
                if endpoint_name == "cashflow_generate":
                    status = "✅" if median_duration < 300 else "❌"
                elif endpoint_name == "scenario_compare":
                    status = "✅" if median_duration < 800 else "❌"
                elif endpoint_name == "pdf_generate":
                    status = "✅" if median_duration < 2500 else "❌"
                else:
                    status = "?"
                
                print(f"{endpoint_name:<20} {len(results):<8} {avg_duration:<10.0f} {median_duration:<12.0f} {p95_duration:<10.0f} {status}")
            else:
                print(f"{endpoint_name:<20} {len(results):<8} {'FAILED':<10} {'FAILED':<12} {'FAILED':<10} ❌")
        
        # Summary line for easy copying
        print(f"\n📋 SUMMARY LINE:")
        successful_cashflow = sum(1 for r in cashflow_results if r["success"])
        successful_compare = sum(1 for r in compare_results if r["success"])
        successful_pdf = sum(1 for r in pdf_results if r["success"])
        
        cashflow_median = statistics.median([r["duration_ms"] for r in cashflow_results if r["success"]]) if successful_cashflow > 0 else 0
        compare_median = statistics.median([r["duration_ms"] for r in compare_results if r["success"]]) if successful_compare > 0 else 0
        pdf_median = statistics.median([r["duration_ms"] for r in pdf_results if r["success"]]) if successful_pdf > 0 else 0
        
        print(f"Success: {success_rate:.1f}% | Cashflow: {cashflow_median:.0f}ms | Compare: {compare_median:.0f}ms | PDF: {pdf_median:.0f}ms")
        
        # Save detailed results
        self.save_results()
    
    def save_results(self):
        """Save detailed results to file"""
        from pathlib import Path
        
        results_dir = Path("artifacts")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / "load_test_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.time(),
                "total_tests": len(self.results),
                "successful_tests": sum(1 for r in self.results if r["success"]),
                "results": self.results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {results_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run load tests for retirement planning API")
    parser.add_argument("--url", default="http://127.0.0.1:8002", help="Base URL for API")
    parser.add_argument("--quick", action="store_true", help="Run quick test (10 calls each)")
    
    args = parser.parse_args()
    
    tester = LoadTester(args.url)
    
    if args.quick:
        print("Running quick load test...")
        # Override for quick testing
        tester.run_quick_test()
    else:
        tester.run_load_test()


if __name__ == "__main__":
    main()
