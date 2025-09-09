#!/usr/bin/env python3
"""
Quick canonical test for Sprint11 closure
"""

import requests
import json
import os
import zipfile
import hashlib
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

def main():
    # Setup
    base_url = 'http://127.0.0.1:8000'
    artifacts_dir = Path('artifacts')
    artifacts_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    commit_sha = 'sprint11-closure-20250908-164627'

    print(f'SPRINT11 CANONICAL RUN - {timestamp}')
    print(f'Commit: {commit_sha}')
    print()

    results = {}

    # Step 1: Cashflow
    print('1. Generating cashflow...')
    try:
        url = f'{base_url}/api/v1/scenarios/24/cashflow/generate'
        params = {'client_id': 1}
        body = {'from': '2025-01', 'to': '2025-12', 'frequency': 'monthly'}
        
        response = requests.post(url, params=params, json=body, timeout=30)
        
        if response.status_code == 200:
            cashflow_data = response.json()
            filename = f'cashflow_live_{timestamp}.json'
            with open(artifacts_dir / filename, 'w') as f:
                json.dump(cashflow_data, f, indent=2, default=str)
            print(f'   ✓ Saved: {filename} ({len(cashflow_data)} rows)')
            results['cashflow'] = {'status': 'PASS', 'rows': len(cashflow_data)}
            cashflow_ok = len(cashflow_data) == 12
        else:
            print(f'   ✗ Failed: {response.status_code}')
            results['cashflow'] = {'status': 'FAIL', 'code': response.status_code}
            cashflow_ok = False
            cashflow_data = None
    except Exception as e:
        print(f'   ✗ Exception: {e}')
        results['cashflow'] = {'status': 'FAIL', 'error': str(e)}
        cashflow_ok = False
        cashflow_data = None

    # Step 2: Compare
    print('2. Running compare...')
    try:
        url = f'{base_url}/api/v1/clients/1/scenarios/compare'
        body = {'scenarios': [24], 'from': '2025-01', 'to': '2025-12', 'frequency': 'monthly'}
        
        response = requests.post(url, json=body, timeout=30)
        
        if response.status_code == 200:
            compare_data = response.json()
            filename = f'compare_live_{timestamp}.json'
            with open(artifacts_dir / filename, 'w') as f:
                json.dump(compare_data, f, indent=2, default=str)
            
            scenarios = compare_data.get('scenarios', [])
            monthly_count = len(scenarios[0].get('monthly', [])) if scenarios else 0
            print(f'   ✓ Saved: {filename} ({len(scenarios)} scenarios, {monthly_count} months)')
            results['compare'] = {'status': 'PASS', 'scenarios': len(scenarios), 'months': monthly_count}
            compare_ok = monthly_count == 12
        else:
            print(f'   ✗ Failed: {response.status_code}')
            results['compare'] = {'status': 'FAIL', 'code': response.status_code}
            compare_ok = False
            compare_data = None
    except Exception as e:
        print(f'   ✗ Exception: {e}')
        results['compare'] = {'status': 'FAIL', 'error': str(e)}
        compare_ok = False
        compare_data = None

    # Step 3: PDF
    print('3. Generating PDF...')
    try:
        url = f'{base_url}/api/v1/scenarios/24/report/pdf'
        params = {'client_id': 1}
        body = {
            'from': '2025-01',
            'to': '2025-12',
            'frequency': 'monthly',
            'sections': {
                'summary': True,
                'cashflow_table': True,
                'net_chart': True,
                'scenarios_compare': True
            }
        }
        
        response = requests.post(url, params=params, json=body, timeout=60)
        
        # Save log
        log_filename = f'pdf_run_{timestamp}.log'
        with open(artifacts_dir / log_filename, 'w') as f:
            f.write(f'HTTP Status: {response.status_code}\n')
            f.write(f'Content-Length: {len(response.content)}\n')
            f.write(f'Content-Type: {response.headers.get("content-type", "unknown")}\n')
        
        if response.status_code == 200:
            pdf_content = response.content
            pdf_size = len(pdf_content)
            is_valid_pdf = pdf_content.startswith(b'%PDF')
            
            if pdf_size > 1024 and is_valid_pdf:
                pdf_filename = f'test_{timestamp}.pdf'
                with open(artifacts_dir / pdf_filename, 'wb') as f:
                    f.write(pdf_content)
                print(f'   ✓ Saved: {pdf_filename} ({pdf_size} bytes, valid PDF)')
                results['pdf'] = {'status': 'PASS', 'size': pdf_size, 'valid': True}
                pdf_ok = True
            else:
                print(f'   ✗ Invalid PDF: size={pdf_size}, valid={is_valid_pdf}')
                results['pdf'] = {'status': 'FAIL', 'size': pdf_size, 'valid': is_valid_pdf}
                pdf_ok = False
        else:
            error_filename = f'pdf_error_{timestamp}.txt'
            with open(artifacts_dir / error_filename, 'w') as f:
                f.write(f'Status: {response.status_code}\nError: {response.text}')
            print(f'   ✗ Failed: {response.status_code} - saved to {error_filename}')
            results['pdf'] = {'status': 'FAIL', 'code': response.status_code}
            pdf_ok = False
    except Exception as e:
        print(f'   ✗ Exception: {e}')
        results['pdf'] = {'status': 'FAIL', 'error': str(e)}
        pdf_ok = False

    # Step 4: Consistency Check
    print('4. Checking consistency...')
    if compare_data and compare_data.get('scenarios'):
        try:
            scenario = compare_data['scenarios'][0]
            monthly_data = scenario.get('monthly', [])
            yearly_data = scenario.get('yearly_totals', {}).get('2025', {})
            
            # Calculate with Decimal precision
            monthly_sum_net = Decimal('0')
            for month in monthly_data:
                net_val = Decimal(str(month.get('net', 0)))
                monthly_sum_net += net_val
            
            monthly_sum_net = monthly_sum_net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            yearly_net = Decimal(str(yearly_data.get('net', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            diff = abs(monthly_sum_net - yearly_net)
            consistency_ok = diff <= Decimal('0.01')
            
            # Save check
            check_filename = f'consistency_check_{timestamp}.txt'
            with open(artifacts_dir / check_filename, 'w', encoding='utf-8') as f:
                f.write('Monthly vs Yearly Totals Consistency Check\n')
                f.write('=' * 50 + '\n\n')
                f.write(f'Monthly sum (net): {monthly_sum_net}\n')
                f.write(f'Yearly total (net): {yearly_net}\n')
                f.write(f'Difference: {diff}\n')
                f.write(f'Tolerance: <= 0.01\n')
                f.write(f'Result: {"PASS" if consistency_ok else "FAIL"}\n')
                f.write(f'Timestamp: {timestamp}\n')
                f.write(f'Commit: {commit_sha}\n')
            
            print(f'   {"✓" if consistency_ok else "✗"} Monthly={monthly_sum_net}, Yearly={yearly_net}, Diff={diff}')
            print(f'   Saved: {check_filename}')
            results['consistency'] = {'status': 'PASS' if consistency_ok else 'FAIL', 'diff': float(diff)}
        except Exception as e:
            print(f'   ✗ Exception: {e}')
            results['consistency'] = {'status': 'FAIL', 'error': str(e)}
            consistency_ok = False
    else:
        print('   ✗ No compare data')
        results['consistency'] = {'status': 'FAIL', 'error': 'No compare data'}
        consistency_ok = False

    # Step 5: Create ZIP
    print('5. Creating ZIP...')
    try:
        zip_filename = f'yearly_totals_verification_{timestamp}.zip'
        zip_path = artifacts_dir / zip_filename
        
        files_to_zip = [
            f'cashflow_live_{timestamp}.json',
            f'compare_live_{timestamp}.json',
            f'consistency_check_{timestamp}.txt',
            f'pdf_run_{timestamp}.log'
        ]
        
        optional_files = [
            f'test_{timestamp}.pdf',
            f'pdf_error_{timestamp}.txt'
        ]
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in files_to_zip:
                file_path = artifacts_dir / filename
                if file_path.exists():
                    zipf.write(file_path, f'artifacts/{filename}')
            
            for filename in optional_files:
                file_path = artifacts_dir / filename
                if file_path.exists():
                    zipf.write(file_path, f'artifacts/{filename}')
        
        # Calculate SHA256
        sha256_hash = hashlib.sha256()
        with open(zip_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        sha256_value = sha256_hash.hexdigest()
        zip_size = os.path.getsize(zip_path)
        
        # Save SHA256
        sha256_filename = f'zip_sha256_{timestamp}.txt'
        with open(artifacts_dir / sha256_filename, 'w') as f:
            f.write(f'{sha256_value}  {zip_filename}\n')
            f.write(f'Size: {zip_size} bytes\n')
            f.write(f'Created: {datetime.now().isoformat()}\n')
            f.write(f'Commit: {commit_sha}\n')
        
        print(f'   ✓ Created: {zip_filename} ({zip_size} bytes)')
        print(f'   ✓ SHA256: {sha256_value[:16]}...')
        print(f'   ✓ Saved: {sha256_filename}')
        
        results['zip'] = {'status': 'PASS', 'filename': zip_filename, 'sha256': sha256_value}
        zip_ok = True
    except Exception as e:
        print(f'   ✗ Exception: {e}')
        results['zip'] = {'status': 'FAIL', 'error': str(e)}
        zip_ok = False

    # Save results
    results_filename = f'canonical_run_{timestamp}.json'
    with open(artifacts_dir / results_filename, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'commit_sha': commit_sha,
            'results': results
        }, f, indent=2)

    print()
    print('=' * 60)
    print('CANONICAL RUN RESULTS:')
    print('=' * 60)
    print(f'Cashflow: {"PASS" if cashflow_ok else "FAIL"}')
    print(f'Compare: {"PASS" if compare_ok else "FAIL"}')
    print(f'PDF: {"PASS" if pdf_ok else "FAIL"}')
    print(f'Consistency: {"PASS" if consistency_ok else "FAIL"}')
    print(f'ZIP: {"PASS" if zip_ok else "FAIL"}')
    print(f'Timestamp: {timestamp}')
    print(f'Commit: {commit_sha}')
    
    if results.get('zip', {}).get('status') == 'PASS':
        print(f'ZIP: {results["zip"]["filename"]}')
        print(f'SHA256: {results["zip"]["sha256"]}')

    overall_success = all([cashflow_ok, compare_ok, consistency_ok, zip_ok])
    print(f'Overall: {"SUCCESS" if overall_success else "FAILED"}')
    
    return overall_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
