#!/usr/bin/env python3
"""
Comprehensive test of the eligibility and rights fixation system
"""

import requests
import json
from datetime import datetime

def test_comprehensive_eligibility():
    """Test the complete eligibility and rights fixation workflow"""
    base_url = "http://localhost:8005"
    
    print("=== Comprehensive Eligibility and Rights Fixation Test ===")
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test clients data
    test_cases = [
        {
            "client_id": 1,
            "description": "Client 1 (Male, 67, with pension) - Should be ELIGIBLE",
            "expected_status": 200
        },
        {
            "client_id": 2, 
            "description": "Client 2 (Female, 63, with pension) - Should be ELIGIBLE",
            "expected_status": 200
        }
    ]
    
    results = {"passed": 0, "failed": 0, "details": []}
    
    for test_case in test_cases:
        client_id = test_case["client_id"]
        description = test_case["description"]
        expected_status = test_case["expected_status"]
        
        print(f"\n--- Testing {description} ---")
        
        # Step 1: Check if client has grants
        print(f"1. Checking grants for client {client_id}...")
        try:
            grants_response = requests.get(f"{base_url}/api/v1/clients/{client_id}/grants")
            if grants_response.status_code == 200:
                grants = grants_response.json()
                print(f"   ✓ Found {len(grants)} grants")
                has_grants = len(grants) > 0
            else:
                print(f"   ✗ Failed to get grants: {grants_response.status_code}")
                has_grants = False
        except Exception as e:
            print(f"   ✗ Error getting grants: {e}")
            has_grants = False
        
        # Step 2: Test rights fixation calculation
        print(f"2. Testing rights fixation calculation...")
        try:
            fixation_response = requests.post(f"{base_url}/api/v1/rights-fixation/calculate", 
                                            json={"client_id": client_id})
            actual_status = fixation_response.status_code
            
            print(f"   Status: {actual_status} (expected: {expected_status})")
            
            if actual_status == expected_status:
                print("   ✓ Status code matches expectation")
                
                if actual_status == 200:
                    # Eligible client - check response structure
                    data = fixation_response.json()
                    required_fields = ["grants", "exemption_summary", "eligibility_date"]
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if not missing_fields:
                        print("   ✓ Response structure is correct")
                        print(f"   ✓ Processed {len(data.get('grants', []))} grants")
                        results["passed"] += 1
                        test_result = "PASS"
                    else:
                        print(f"   ✗ Missing fields: {missing_fields}")
                        results["failed"] += 1
                        test_result = "FAIL"
                        
                elif actual_status == 409:
                    # Ineligible client - check error structure
                    response_data = fixation_response.json()
                    # FastAPI HTTPException wraps the detail in a "detail" field
                    data = response_data.get("detail", response_data)
                    required_fields = ["error", "reasons", "eligibility_date", "eligibility_check"]
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if not missing_fields:
                        print("   ✓ Error response structure is correct")
                        print(f"   ✓ Error: {data.get('error', 'N/A')}")
                        print(f"   ✓ Reasons: {len(data.get('reasons', []))} reason(s)")
                        print(f"   ✓ Eligibility date: {data.get('eligibility_date', 'N/A')}")
                        
                        # Test JSON serialization
                        try:
                            json.dumps(data)
                            print("   ✓ JSON serialization works correctly")
                            results["passed"] += 1
                            test_result = "PASS"
                        except Exception as json_err:
                            print(f"   ✗ JSON serialization failed: {json_err}")
                            results["failed"] += 1
                            test_result = "FAIL"
                    else:
                        print(f"   ✗ Missing error fields: {missing_fields}")
                        results["failed"] += 1
                        test_result = "FAIL"
                else:
                    print(f"   ? Unexpected status code: {actual_status}")
                    results["failed"] += 1
                    test_result = "FAIL"
            else:
                print(f"   ✗ Status code mismatch: got {actual_status}, expected {expected_status}")
                results["failed"] += 1
                test_result = "FAIL"
                
        except Exception as e:
            print(f"   ✗ Error in rights fixation test: {e}")
            results["failed"] += 1
            test_result = "FAIL"
        
        results["details"].append({
            "client_id": client_id,
            "description": description,
            "has_grants": has_grants,
            "expected_status": expected_status,
            "actual_status": actual_status if 'actual_status' in locals() else None,
            "result": test_result
        })
        
        print(f"   Result: {test_result}")
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {results['passed'] + results['failed']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success rate: {(results['passed'] / (results['passed'] + results['failed']) * 100):.1f}%")
    
    # Detailed results
    print(f"\nDetailed Results:")
    for detail in results["details"]:
        status_icon = "✓" if detail["result"] == "PASS" else "✗"
        print(f"  {status_icon} Client {detail['client_id']}: {detail['result']}")
    
    overall_success = results['failed'] == 0
    print(f"\nOverall Result: {'SUCCESS' if overall_success else 'FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    success = test_comprehensive_eligibility()
    exit(0 if success else 1)
