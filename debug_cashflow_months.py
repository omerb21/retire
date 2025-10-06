#!/usr/bin/env python3
"""Debug script to check why cashflow is only returning 3 months instead of 12"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.cashflow_service import generate_cashflow, _month_iter
from app.services.case_service import detect_case

def debug_month_generation():
    """Test month generation logic"""
    print("=== Testing Month Generation ===")
    
    # Test month iterator
    months = _month_iter("2025-01", "2025-12")
    print(f"Month iterator returned {len(months)} months:")
    for i, month in enumerate(months):
        print(f"  {i+1}: {month}")
    
    return len(months) == 12

def debug_cashflow_generation():
    """Test full cashflow generation"""
    print("\n=== Testing Cashflow Generation ===")
    
    try:
        db = SessionLocal()
        
        # Test parameters
        client_id = 1
        scenario_id = 24
        from_ym = "2025-01"
        to_ym = "2025-12"
        
        print(f"Testing with client_id={client_id}, scenario_id={scenario_id}")
        print(f"Date range: {from_ym} to {to_ym}")
        
        # Detect case
        case_result = detect_case(db, client_id)
        case_id = case_result.case_id
        print(f"Detected case_id: {case_id}")
        
        # Generate cashflow
        print("Calling generate_cashflow...")
        cashflow_data = generate_cashflow(
            db=db,
            client_id=client_id,
            scenario_id=scenario_id,
            start_ym=from_ym,
            end_ym=to_ym,
            case_id=case_id
        )
        
        print(f"Cashflow returned {len(cashflow_data)} rows:")
        for i, row in enumerate(cashflow_data):
            date_str = row.get('date', 'NO_DATE')
            inflow = row.get('inflow', 0)
            outflow = row.get('outflow', 0)
            net = row.get('net', 0)
            print(f"  {i+1}: {date_str} | inflow={inflow} | outflow={outflow} | net={net}")
        
        db.close()
        return len(cashflow_data)
        
    except Exception as e:
        print(f"Error in cashflow generation: {e}")
        import traceback
        traceback.print_exc()
        return 0

def debug_compare_service():
    """Test compare service directly"""
    print("\n=== Testing Compare Service ===")
    
    try:
        from app.services.compare_service import compare_scenarios
        
        db = SessionLocal()
        
        result = compare_scenarios(
            db_session=db,
            client_id=1,
            scenario_ids=[24],
            from_yyyymm="2025-01",
            to_yyyymm="2025-12",
            frequency="monthly"
        )
        
        print("Compare service result:")
        print(f"Number of scenarios: {len(result.get('scenarios', []))}")
        
        if result.get('scenarios'):
            scenario = result['scenarios'][0]
            monthly_data = scenario.get('monthly', [])
            print(f"Monthly data rows: {len(monthly_data)}")
            
            for i, row in enumerate(monthly_data):
                date_str = row.get('date', 'NO_DATE')
                net = row.get('net', 0)
                print(f"  {i+1}: {date_str} | net={net}")
        
        db.close()
        return len(monthly_data) if result.get('scenarios') else 0
        
    except Exception as e:
        print(f"Error in compare service: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    print("=== CASHFLOW MONTHS DEBUG ===")
    
    # Test 1: Month generation
    month_test_ok = debug_month_generation()
    print(f"Month generation test: {'PASS' if month_test_ok else 'FAIL'}")
    
    # Test 2: Cashflow generation
    cashflow_months = debug_cashflow_generation()
    print(f"Cashflow generation returned: {cashflow_months} months")
    
    # Test 3: Compare service
    compare_months = debug_compare_service()
    print(f"Compare service returned: {compare_months} months")
    
    print("\n=== SUMMARY ===")
    print(f"Expected: 12 months")
    print(f"Month iterator: {'OK' if month_test_ok else 'FAIL'}")
    print(f"Cashflow service: {cashflow_months} months")
    print(f"Compare service: {compare_months} months")
    
    if cashflow_months == 12 and compare_months == 12:
        print("✓ All services returning 12 months correctly")
    else:
        print("✗ Issue found - services not returning 12 months")
