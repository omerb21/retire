"""
Comprehensive test suite for retirement planning system
"""
import requests
import json
import time
from pathlib import Path
import subprocess
import sys

class RetirementSystemTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        
    def log_test(self, test_name, status, details=""):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def test_server_health(self):
        """Test basic server health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                pdf_available = data.get("pdf_available", False)
                self.log_test("Server Health", "PASS", f"PDF available: {pdf_available}")
                return True
            else:
                self.log_test("Server Health", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Server Health", "FAIL", f"Connection error: {e}")
            return False
    
    def test_client_crud(self):
        """Test client CRUD operations"""
        try:
            # Test GET clients
            response = requests.get(f"{self.base_url}/api/v1/clients")
            if response.status_code != 200:
                self.log_test("Client CRUD - List", "FAIL", f"Status: {response.status_code}")
                return False
            
            clients = response.json()
            if "clients" not in clients:
                self.log_test("Client CRUD - List", "FAIL", "Missing clients field")
                return False
            
            # Test GET specific client
            if clients["clients"]:
                client_id = clients["clients"][0]["id"]
                response = requests.get(f"{self.base_url}/api/v1/clients/{client_id}")
                if response.status_code == 200:
                    self.log_test("Client CRUD", "PASS", f"Found {len(clients['clients'])} clients")
                    return True
                else:
                    self.log_test("Client CRUD - Get", "FAIL", f"Status: {response.status_code}")
                    return False
            else:
                self.log_test("Client CRUD", "PASS", "No clients found (empty DB)")
                return True
                
        except Exception as e:
            self.log_test("Client CRUD", "FAIL", f"Error: {e}")
            return False
    
    def test_scenarios_api(self):
        """Test scenarios API"""
        try:
            # Test scenario endpoint
            response = requests.get(f"{self.base_url}/api/v1/scenarios/24")
            if response.status_code == 200:
                scenario = response.json()
                if "cashflow" in scenario:
                    cashflow_count = len(scenario["cashflow"])
                    self.log_test("Scenarios API", "PASS", f"Scenario 24 has {cashflow_count} months")
                    return True
                else:
                    self.log_test("Scenarios API", "FAIL", "Missing cashflow data")
                    return False
            else:
                self.log_test("Scenarios API", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Scenarios API", "FAIL", f"Error: {e}")
            return False
    
    def test_cashflow_data(self):
        """Test cashflow data integrity"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/scenarios/24/cashflow")
            if response.status_code == 200:
                data = response.json()
                cashflow = data.get("cashflow", [])
                months_count = data.get("months_count", 0)
                
                if months_count == 12:
                    # Verify data consistency
                    total_net = sum(month.get("net", 0) for month in cashflow)
                    self.log_test("Cashflow Data", "PASS", f"12/12 months, total net: ₪{total_net:,}")
                    return True
                else:
                    self.log_test("Cashflow Data", "FAIL", f"Expected 12 months, got {months_count}")
                    return False
            else:
                self.log_test("Cashflow Data", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Cashflow Data", "FAIL", f"Error: {e}")
            return False
    
    def test_pdf_generation(self):
        """Test PDF generation"""
        try:
            pdf_request = {
                "from_": "2025-01",
                "to": "2025-12",
                "frequency": "monthly"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/scenarios/24/report/pdf?client_id=1",
                json=pdf_request,
                timeout=30
            )
            
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "pdf" in content_type.lower():
                    pdf_size = len(response.content)
                    # Verify it's a valid PDF
                    if response.content[:4] == b"%PDF":
                        self.log_test("PDF Generation", "PASS", f"Valid PDF ({pdf_size} bytes)")
                        return True
                    else:
                        self.log_test("PDF Generation", "FAIL", "Invalid PDF format")
                        return False
                else:
                    self.log_test("PDF Generation", "FAIL", f"Wrong content type: {content_type}")
                    return False
            else:
                self.log_test("PDF Generation", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("PDF Generation", "FAIL", f"Error: {e}")
            return False
    
    def test_tax_data_apis(self):
        """Test tax data APIs"""
        try:
            # Test severance caps
            response = requests.get(f"{self.base_url}/api/v1/tax-data/severance-caps")
            if response.status_code != 200:
                self.log_test("Tax Data - Severance", "FAIL", f"Status: {response.status_code}")
                return False
            
            caps = response.json()
            monthly_cap = caps.get("monthly_cap", 0)
            
            # Test tax brackets
            response = requests.get(f"{self.base_url}/api/v1/tax-data/tax-brackets")
            if response.status_code != 200:
                self.log_test("Tax Data - Brackets", "FAIL", f"Status: {response.status_code}")
                return False
            
            brackets = response.json()
            bracket_count = len(brackets.get("brackets", []))
            
            self.log_test("Tax Data APIs", "PASS", f"Cap: ₪{monthly_cap:,}, {bracket_count} brackets")
            return True
            
        except Exception as e:
            self.log_test("Tax Data APIs", "FAIL", f"Error: {e}")
            return False
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Comprehensive Test Suite")
        print("=" * 50)
        
        tests = [
            self.test_server_health,
            self.test_client_crud,
            self.test_scenarios_api,
            self.test_cashflow_data,
            self.test_pdf_generation,
            self.test_tax_data_apis
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED - System is fully functional!")
            return True
        else:
            print(f"⚠️  {total - passed} tests failed - Review issues above")
            return False
    
    def generate_report(self):
        """Generate detailed test report"""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(self.test_results),
            "passed": len([r for r in self.test_results if r["status"] == "PASS"]),
            "failed": len([r for r in self.test_results if r["status"] == "FAIL"]),
            "results": self.test_results
        }
        
        # Save to file
        with open("test_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed report saved to: test_report.json")
        return report

def main():
    """Main test runner"""
    tester = RetirementSystemTester()
    
    # Check if server is running
    print("🔍 Checking server availability...")
    if not tester.test_server_health():
        print("\n❌ Server not available. Please start the server first:")
        print("   python minimal_working_server.py")
        return False
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Generate report
    tester.generate_report()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
