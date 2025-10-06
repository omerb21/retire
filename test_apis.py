#!/usr/bin/env python3
"""
Test script for all tax data APIs
"""
import requests
import json

def test_tax_apis():
    base_url = 'http://localhost:8000/api/v1'
    print('=== Testing Tax Data APIs ===\n')

    # 1. Severance cap
    try:
        r = requests.get(f'{base_url}/tax-data/severance-cap')
        print(f'1. Severance Cap: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   Monthly cap: {data["monthly_cap"]} NIS')
            print(f'   Annual cap: {data["annual_cap"]} NIS')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print()

    # 2. Tax brackets  
    try:
        r = requests.get(f'{base_url}/tax-data/tax-brackets')
        print(f'2. Tax Brackets: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   Brackets count: {len(data["brackets"])}')
            print(f'   First bracket: {data["brackets"][0]["rate"]*100}% up to {data["brackets"][0]["max_income"]} NIS')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print()

    # 3. CPI data
    try:
        r = requests.get(f'{base_url}/tax-data/cpi?start_year=2023&end_year=2025')
        print(f'3. CPI Data: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   Records: {data["records_count"]}')
            if data["data"]:
                print(f'   Latest CPI: {data["data"][-1]["index_value"]} ({data["data"][-1]["year"]})')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print()

    # 4. Severance exemption
    try:
        r = requests.get(f'{base_url}/tax-data/severance-exemption?service_years=10')
        print(f'4. Severance Exemption: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   For 10 years service: {data["total_exemption"]} NIS')
            print(f'   Calculation: {data["calculation"]}')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print()

    # 5. Indexation factor
    try:
        r = requests.get(f'{base_url}/tax-data/indexation-factor?base_year=2020&target_year=2025')
        print(f'5. Indexation Factor: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   2020 to 2025 factor: {data["indexation_factor"]:.4f}')
            print(f'   Percentage change: {data["percentage_change"]:.2f}%')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print()

    # 6. Tax data summary
    try:
        r = requests.get(f'{base_url}/tax-data/summary')
        print(f'6. Tax Data Summary: {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            print(f'   Year: {data["year"]}')
            print(f'   Severance cap (monthly): {data["severance_cap"]["monthly"]} NIS')
            print(f'   Tax brackets: {data["tax_brackets_count"]}')
            print(f'   Current CPI: {data["current_cpi"]}')
        else:
            print(f'   Error: {r.text}')
    except Exception as e:
        print(f'   Exception: {e}')

    print('\n=== API Testing Complete ===')

if __name__ == '__main__':
    test_tax_apis()
