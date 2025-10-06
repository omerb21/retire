"""
Full system integration test
Tests all components of the retirement planning system end-to-end
"""
import sys
import os
import requests
import json
from datetime import date, datetime

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_CLIENT_DATA = {
    "id_number": "123456782",
    "full_name": "ישראל בדיקה",
    "first_name": "ישראל",
    "last_name": "בדיקה",
    "birth_date": "1970-01-01",
    "gender": "male",
    "marital_status": "married",
    "email": "test@example.com",
    "phone": "054-1234567",
    "address": "רחוב הבדיקה 1, תל אביב",
    "retirement_target_date": "2030-01-01",
    "is_active": True,
    "notes": "לקוח לבדיקה"
}

class SystemTester:
    def __init__(self):
        self.client_id = None
        self.current_employer_id = None
        self.grant_ids = []
        self.pension_fund_ids = []
        self.scenario_ids = []
        self.errors = []
        self.successes = []

    def log_success(self, message):
        print(f"✓ {message}")
        self.successes.append(message)

    def log_error(self, message):
        print(f"✗ {message}")
        self.errors.append(message)

    def test_api_health(self):
        """Test if API is running"""
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                self.log_success("API Health Check")
                return True
            else:
                self.log_error(f"API Health Check failed: {response.status_code}")
                return False
        except Exception as e:
            self.log_error(f"API Health Check failed: {e}")
            return False

    def test_client_crud(self):
        """Test client CRUD operations"""
        try:
            # Create client
            response = requests.post(f"{API_BASE_URL}/api/v1/clients", json=TEST_CLIENT_DATA)
            if response.status_code == 201:
                client_data = response.json()
                self.client_id = client_data["id"]
                self.log_success(f"Client created with ID: {self.client_id}")
            else:
                self.log_error(f"Client creation failed: {response.status_code} - {response.text}")
                return False

            # Get client
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}")
            if response.status_code == 200:
                self.log_success("Client retrieval")
            else:
                self.log_error(f"Client retrieval failed: {response.status_code}")
                return False

            # Update client
            update_data = {"notes": "לקוח מעודכן לבדיקה"}
            response = requests.patch(f"{API_BASE_URL}/api/v1/clients/{self.client_id}", json=update_data)
            if response.status_code == 200:
                self.log_success("Client update")
            else:
                self.log_error(f"Client update failed: {response.status_code}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Client CRUD test failed: {e}")
            return False

    def test_current_employer(self):
        """Test current employer operations"""
        try:
            employer_data = {
                "employer_name": "חברת בדיקה בע\"מ",
                "start_date": "2020-01-01",
                "monthly_salary": 25000,
                "severance_balance": 200000
            }

            # Create current employer
            response = requests.post(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/current-employer", json=employer_data)
            if response.status_code == 201:
                employer = response.json()
                self.current_employer_id = employer["id"]
                self.log_success(f"Current employer created with ID: {self.current_employer_id}")
            else:
                self.log_error(f"Current employer creation failed: {response.status_code} - {response.text}")
                return False

            # Get current employer
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/current-employer")
            if response.status_code == 200:
                self.log_success("Current employer retrieval")
            else:
                self.log_error(f"Current employer retrieval failed: {response.status_code}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Current employer test failed: {e}")
            return False

    def test_grants(self):
        """Test grants operations"""
        try:
            grant_data = {
                "employer_name": "חברה קודמת",
                "grant_type": "severance",
                "grant_date": "2023-01-01",
                "amount": 150000,
                "service_years": 10,
                "reason": "פיצויים"
            }

            # Create grant
            response = requests.post(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/grants", json=grant_data)
            if response.status_code == 201:
                grant = response.json()
                self.grant_ids.append(grant["id"])
                self.log_success(f"Grant created with ID: {grant['id']}")
            else:
                self.log_error(f"Grant creation failed: {response.status_code} - {response.text}")
                return False

            # Get grants
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/grants")
            if response.status_code == 200:
                grants = response.json()
                self.log_success(f"Grants retrieval: {len(grants)} grants found")
            else:
                self.log_error(f"Grants retrieval failed: {response.status_code}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Grants test failed: {e}")
            return False

    def test_pension_funds(self):
        """Test pension funds operations"""
        try:
            pension_data = {
                "fund_name": "קרן פנסיה לבדיקה",
                "fund_number": "12345",
                "base_amount": 500000,
                "input_mode": "manual",
                "indexation_method": "cpi"
            }

            # Create pension fund
            response = requests.post(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/pension-funds", json=pension_data)
            if response.status_code == 201:
                fund = response.json()
                self.pension_fund_ids.append(fund["id"])
                self.log_success(f"Pension fund created with ID: {fund['id']}")
            else:
                self.log_error(f"Pension fund creation failed: {response.status_code} - {response.text}")
                return False

            # Get pension funds
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/pension-funds")
            if response.status_code == 200:
                funds = response.json()
                self.log_success(f"Pension funds retrieval: {len(funds)} funds found")
            else:
                self.log_error(f"Pension funds retrieval failed: {response.status_code}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Pension funds test failed: {e}")
            return False

    def test_scenarios(self):
        """Test scenarios operations"""
        try:
            scenario_data = {
                "scenario_name": "תרחיש בדיקה",
                "apply_tax_planning": True,
                "apply_capitalization": False,
                "apply_exemption_shield": True,
                "parameters": {
                    "retirement_age": 67,
                    "monthly_expenses": 15000
                }
            }

            # Create scenario
            response = requests.post(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/scenarios", json=scenario_data)
            if response.status_code == 201:
                scenario = response.json()
                self.scenario_ids.append(scenario["id"])
                self.log_success(f"Scenario created with ID: {scenario['id']}")
            else:
                self.log_error(f"Scenario creation failed: {response.status_code} - {response.text}")
                return False

            # Get scenarios
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/scenarios")
            if response.status_code == 200:
                scenarios = response.json()
                self.log_success(f"Scenarios retrieval: {len(scenarios)} scenarios found")
            else:
                self.log_error(f"Scenarios retrieval failed: {response.status_code}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Scenarios test failed: {e}")
            return False

    def test_fixation(self):
        """Test fixation operations"""
        try:
            # Test fixation compute
            response = requests.post(f"{API_BASE_URL}/api/v1/fixation/{self.client_id}/compute")
            if response.status_code == 200:
                result = response.json()
                self.log_success("Fixation computation")
            else:
                self.log_error(f"Fixation computation failed: {response.status_code} - {response.text}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Fixation test failed: {e}")
            return False

    def test_reports(self):
        """Test reports generation"""
        try:
            if not self.scenario_ids:
                self.log_error("No scenarios available for report generation")
                return False

            report_data = {
                "scenario_ids": self.scenario_ids,
                "report_type": "summary",
                "include_charts": True,
                "include_cashflow": True
            }

            # Test report preview
            scenario_ids_str = ",".join(map(str, self.scenario_ids))
            response = requests.get(f"{API_BASE_URL}/api/v1/clients/{self.client_id}/reports/preview?scenario_ids={scenario_ids_str}")
            if response.status_code == 200:
                self.log_success("Report preview")
            else:
                self.log_error(f"Report preview failed: {response.status_code} - {response.text}")
                return False

            return True
        except Exception as e:
            self.log_error(f"Reports test failed: {e}")
            return False

    def cleanup(self):
        """Clean up test data"""
        try:
            if self.client_id:
                response = requests.delete(f"{API_BASE_URL}/api/v1/clients/{self.client_id}")
                if response.status_code == 204:
                    self.log_success("Test client cleanup")
                else:
                    self.log_error(f"Test client cleanup failed: {response.status_code}")
        except Exception as e:
            self.log_error(f"Cleanup failed: {e}")

    def run_all_tests(self):
        """Run all system tests"""
        print("🚀 Starting Full System Integration Test")
        print("=" * 50)

        # Test API health first
        if not self.test_api_health():
            print("\n❌ API is not running. Please start the backend server first.")
            return False

        # Run all tests
        tests = [
            ("Client CRUD", self.test_client_crud),
            ("Current Employer", self.test_current_employer),
            ("Grants", self.test_grants),
            ("Pension Funds", self.test_pension_funds),
            ("Scenarios", self.test_scenarios),
            ("Fixation", self.test_fixation),
            ("Reports", self.test_reports),
        ]

        for test_name, test_func in tests:
            print(f"\n📋 Testing {test_name}...")
            try:
                test_func()
            except Exception as e:
                self.log_error(f"{test_name} test failed with exception: {e}")

        # Cleanup
        print(f"\n🧹 Cleaning up...")
        self.cleanup()

        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        print(f"✅ Successful tests: {len(self.successes)}")
        print(f"❌ Failed tests: {len(self.errors)}")

        if self.errors:
            print("\n❌ Errors:")
            for error in self.errors:
                print(f"  - {error}")

        if len(self.errors) == 0:
            print("\n🎉 All tests passed! The system is working correctly.")
            return True
        else:
            print(f"\n⚠️  {len(self.errors)} tests failed. Please check the errors above.")
            return False

def main():
    """Main test function"""
    tester = SystemTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ System is ready for use!")
        exit(0)
    else:
        print("\n❌ System has issues that need to be resolved.")
        exit(1)

if __name__ == "__main__":
    main()
