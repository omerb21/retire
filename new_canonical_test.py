#!/usr/bin/env python3
"""
New Canonical Test for FastAPI system with full CRUD flow
Tests: create client → create employer → call generate_cashflow → export_pdf
"""

import requests
import json
import os
import zipfile
import hashlib
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

def main():
    # Setup
    base_url = 'http://127.0.0.1:8000'
    artifacts_dir = Path('artifacts')
    artifacts_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    commit_sha = 'new-api-system-20250909'

    print(f'NEW CANONICAL TEST RUN - {timestamp}')
    print(f'Commit: {commit_sha}')
    print()

    results = {}
    overall_success = True

    # Step 1: Health Check
    print('1. Health check...')
    try:
        response = requests.get(f'{base_url}/health', timeout=10)
        if response.status_code == 200:
            print('   ✓ API server is running')
            results['health'] = {'status': 'PASS'}
        else:
            print(f'   ✗ Health check failed: {response.status_code}')
            results['health'] = {'status': 'FAIL', 'code': response.status_code}
            overall_success = False
    except Exception as e:
        print(f'   ✗ Cannot connect to API: {e}')
        results['health'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False
        return save_results_and_exit(results, artifacts_dir, timestamp, commit_sha, False)

    # Step 2: Create Client
    print('2. Creating client...')
    try:
        client_data = {
            "id_number": "123456789",
            "full_name": "ישראל ישראלי",
            "birth_date": "1970-01-01",
            "email": "test@example.com",
            "phone": "050-1234567"
        }
        
        response = requests.post(f'{base_url}/api/v1/clients', json=client_data, timeout=30)
        
        if response.status_code == 201:
            client = response.json()
            client_id = client['id']
            print(f'   ✓ Client created: ID {client_id}')
            results['client_create'] = {'status': 'PASS', 'client_id': client_id}
        else:
            print(f'   ✗ Failed to create client: {response.status_code}')
            print(f'   Response: {response.text}')
            results['client_create'] = {'status': 'FAIL', 'code': response.status_code}
            overall_success = False
            return save_results_and_exit(results, artifacts_dir, timestamp, commit_sha, False)
            
    except Exception as e:
        print(f'   ✗ Error creating client: {e}')
        results['client_create'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False
        return save_results_and_exit(results, artifacts_dir, timestamp, commit_sha, False)

    # Step 3: Create Current Employer
    print('3. Creating current employer...')
    try:
        employer_data = {
            "employer_name": "חברת טכנולוגיה בע\"מ",
            "start_date": "2020-01-01",
            "last_salary": 15000.0,
            "average_salary": 14500.0,
            "severance_accrued": 50000.0,
            "continuity_years": 5.0
        }
        
        response = requests.post(
            f'{base_url}/api/v1/clients/{client_id}/current-employer', 
            json=employer_data, 
            timeout=30
        )
        
        if response.status_code == 201:
            employer = response.json()
            employer_id = employer['id']
            print(f'   ✓ Employer created: ID {employer_id}')
            results['employer_create'] = {'status': 'PASS', 'employer_id': employer_id}
        else:
            print(f'   ✗ Failed to create employer: {response.status_code}')
            print(f'   Response: {response.text}')
            results['employer_create'] = {'status': 'FAIL', 'code': response.status_code}
            overall_success = False
            
    except Exception as e:
        print(f'   ✗ Error creating employer: {e}')
        results['employer_create'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False

    # Step 4: Create Scenario with Cashflow
    print('4. Creating scenario with cashflow...')
    try:
        scenario_data = {
            "scenario_name": f"Test Scenario {timestamp}",
            "apply_tax_planning": True,
            "apply_capitalization": False,
            "apply_exemption_shield": True,
            "parameters": json.dumps({
                "retirement_age": 67,
                "current_age": 45,
                "monthly_salary": 15000
            })
        }
        
        response = requests.post(
            f'{base_url}/api/v1/clients/{client_id}/scenarios', 
            json=scenario_data, 
            timeout=30
        )
        
        if response.status_code == 201:
            scenario = response.json()
            scenario_id = scenario['id']
            print(f'   ✓ Scenario created: ID {scenario_id}')
            
            # Get cashflow data
            cashflow_response = requests.get(
                f'{base_url}/api/v1/clients/{client_id}/scenarios/{scenario_id}/cashflow',
                timeout=30
            )
            
            if cashflow_response.status_code == 200:
                cashflow_data = cashflow_response.json()
                
                # Save cashflow
                filename = f'cashflow_{timestamp}.json'
                with open(artifacts_dir / filename, 'w', encoding='utf-8') as f:
                    json.dump(cashflow_data, f, indent=2, default=str, ensure_ascii=False)
                
                monthly_count = len(cashflow_data.get('monthly', []))
                print(f'   ✓ Cashflow generated: {monthly_count} months')
                
                results['scenario_create'] = {
                    'status': 'PASS', 
                    'scenario_id': scenario_id,
                    'months': monthly_count
                }
                
                # Verify 12 months
                if monthly_count == 12:
                    print('   ✓ Correct number of months (12)')
                    results['months_check'] = {'status': 'PASS', 'count': 12}
                else:
                    print(f'   ✗ Expected 12 months, got {monthly_count}')
                    results['months_check'] = {'status': 'FAIL', 'count': monthly_count}
                    overall_success = False
                    
            else:
                print(f'   ✗ Failed to get cashflow: {cashflow_response.status_code}')
                results['scenario_create'] = {'status': 'FAIL', 'code': cashflow_response.status_code}
                overall_success = False
                
        else:
            print(f'   ✗ Failed to create scenario: {response.status_code}')
            print(f'   Response: {response.text}')
            results['scenario_create'] = {'status': 'FAIL', 'code': response.status_code}
            overall_success = False
            
    except Exception as e:
        print(f'   ✗ Error creating scenario: {e}')
        results['scenario_create'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False

    # Step 5: Generate PDF
    print('5. Generating PDF report...')
    try:
        from app.utils.report_export import export_pdf
        
        # Get scenario data for PDF
        scenario_response = requests.get(
            f'{base_url}/api/v1/clients/{client_id}/scenarios/{scenario_id}',
            timeout=30
        )
        
        if scenario_response.status_code == 200:
            scenario_data = scenario_response.json()
            scenarios = [scenario_data]
            
            pdf_path = artifacts_dir / f'test_report_{timestamp}.pdf'
            pdf_result = export_pdf(client_id, scenarios, str(pdf_path))
            
            if pdf_result.get('success'):
                file_size = pdf_result.get('file_size', 0)
                is_valid = pdf_result.get('is_valid_pdf', False)
                
                print(f'   ✓ PDF generated: {file_size} bytes')
                
                if is_valid and file_size > 1024:  # > 1KB and valid PDF
                    print('   ✓ PDF is valid and > 1KB')
                    results['pdf_generate'] = {
                        'status': 'PASS', 
                        'size': file_size,
                        'valid': is_valid
                    }
                else:
                    print(f'   ✗ PDF validation failed: size={file_size}, valid={is_valid}')
                    results['pdf_generate'] = {
                        'status': 'FAIL', 
                        'size': file_size,
                        'valid': is_valid
                    }
                    overall_success = False
            else:
                print(f'   ✗ PDF generation failed: {pdf_result.get("error")}')
                results['pdf_generate'] = {'status': 'FAIL', 'error': pdf_result.get('error')}
                overall_success = False
        else:
            print(f'   ✗ Failed to get scenario for PDF: {scenario_response.status_code}')
            results['pdf_generate'] = {'status': 'FAIL', 'code': scenario_response.status_code}
            overall_success = False
            
    except Exception as e:
        print(f'   ✗ Error generating PDF: {e}')
        results['pdf_generate'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False

    # Step 6: Consistency Check
    print('6. Consistency check...')
    try:
        if 'cashflow_data' in locals() and cashflow_data:
            monthly_data = cashflow_data.get('monthly', [])
            yearly_totals = cashflow_data.get('yearly_totals', {})
            
            if monthly_data and yearly_totals:
                # Calculate sum of monthly net
                monthly_sum = sum(Decimal(str(month.get('net', 0))) for month in monthly_data)
                
                # Get yearly net (assuming 2025)
                yearly_net = Decimal(str(yearly_totals.get('2025', {}).get('net', 0)))
                
                # Calculate difference
                difference = abs(monthly_sum - yearly_net)
                tolerance = Decimal('0.01')
                
                consistency_text = f"""Monthly vs Yearly Totals Consistency Check
==================================================

Monthly sum (net): {monthly_sum}
Yearly total (net): {yearly_net}
Difference: {difference}
Tolerance: <= {tolerance}
Result: {"PASS" if difference <= tolerance else "FAIL"}
Timestamp: {timestamp}
Commit: {commit_sha}
"""
                
                # Save consistency check
                consistency_file = artifacts_dir / f'consistency_check_{timestamp}.txt'
                with open(consistency_file, 'w', encoding='utf-8') as f:
                    f.write(consistency_text)
                
                if difference <= tolerance:
                    print(f'   ✓ Consistency check PASS (diff: {difference})')
                    results['consistency'] = {
                        'status': 'PASS', 
                        'difference': float(difference),
                        'monthly_sum': float(monthly_sum),
                        'yearly_net': float(yearly_net)
                    }
                else:
                    print(f'   ✗ Consistency check FAIL (diff: {difference})')
                    results['consistency'] = {
                        'status': 'FAIL', 
                        'difference': float(difference),
                        'monthly_sum': float(monthly_sum),
                        'yearly_net': float(yearly_net)
                    }
                    overall_success = False
            else:
                print('   ✗ No cashflow data for consistency check')
                results['consistency'] = {'status': 'FAIL', 'error': 'No cashflow data'}
                overall_success = False
        else:
            print('   ✗ No cashflow data available')
            results['consistency'] = {'status': 'FAIL', 'error': 'No cashflow data available'}
            overall_success = False
            
    except Exception as e:
        print(f'   ✗ Error in consistency check: {e}')
        results['consistency'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False

    # Step 7: Create ZIP and SHA256
    print('7. Creating ZIP archive...')
    try:
        zip_filename = f'canonical_test_artifacts_{timestamp}.zip'
        zip_path = artifacts_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all artifacts from this run
            for file_path in artifacts_dir.glob(f'*_{timestamp}.*'):
                if file_path.name != zip_filename:  # Don't include the zip itself
                    zipf.write(file_path, file_path.name)
        
        # Calculate SHA256
        sha256_hash = hashlib.sha256()
        with open(zip_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        sha256_value = sha256_hash.hexdigest()
        
        # Save SHA256
        sha256_file = artifacts_dir / f'zip_sha256_{timestamp}.txt'
        with open(sha256_file, 'w') as f:
            f.write(f'{sha256_value}  {zip_filename}\n')
        
        zip_size = zip_path.stat().st_size
        print(f'   ✓ ZIP created: {zip_filename} ({zip_size} bytes)')
        print(f'   ✓ SHA256: {sha256_value}')
        
        results['zip_create'] = {
            'status': 'PASS',
            'filename': zip_filename,
            'size': zip_size,
            'sha256': sha256_value
        }
        
    except Exception as e:
        print(f'   ✗ Error creating ZIP: {e}')
        results['zip_create'] = {'status': 'FAIL', 'error': str(e)}
        overall_success = False

    return save_results_and_exit(results, artifacts_dir, timestamp, commit_sha, overall_success)


def save_results_and_exit(results, artifacts_dir, timestamp, commit_sha, overall_success):
    """Save results and exit with appropriate code"""
    
    # Save results
    results_file = artifacts_dir / f'canonical_run_{timestamp}.json'
    final_results = {
        'timestamp': timestamp,
        'commit_sha': commit_sha,
        'overall_success': overall_success,
        'results': results
    }
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, default=str, ensure_ascii=False)
    
    # Save commit SHA
    commit_file = artifacts_dir / 'commit_sha.txt'
    with open(commit_file, 'w') as f:
        f.write(commit_sha)
    
    print()
    print('=' * 50)
    if overall_success:
        print('GLOBAL VERDICT: PASS')
        print('All tests completed successfully!')
        exit_code = 0
    else:
        print('GLOBAL VERDICT: FAIL')
        print('Some tests failed. Check results above.')
        exit_code = 1
    
    print(f'Results saved to: {results_file}')
    print('=' * 50)
    
    return exit_code


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print('\nTest interrupted by user')
        sys.exit(1)
    except Exception as e:
        print(f'\nUnexpected error: {e}')
        sys.exit(1)
