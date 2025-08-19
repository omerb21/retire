"""
Simple test script for pension calculation functions
"""
import sys
import os
from datetime import date, timedelta

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing pension calculation functions...")
    
    # Create a mock pension fund object
    class MockPensionFund:
        def __init__(self, input_mode, balance=None, annuity_factor=None, 
                     pension_amount=None, indexation_method="none", 
                     fixed_index_rate=None, pension_start_date=None):
            self.input_mode = input_mode
            self.balance = balance
            self.annuity_factor = annuity_factor
            self.pension_amount = pension_amount
            self.indexation_method = indexation_method
            self.fixed_index_rate = fixed_index_rate
            self.pension_start_date = pension_start_date
    
    # Create mock tax parameters
    class MockTaxParams:
        def __init__(self, annuity_factor=200.0):
            self.annuity_factor = annuity_factor
            self.cpi_series = {
                date(2023, 1, 1): 100.0,
                date(2023, 6, 1): 102.0,
                date(2024, 1, 1): 105.0,
                date(2024, 6, 1): 107.0,
                date(2025, 1, 1): 110.0,
                date(2025, 6, 1): 112.0,
            }
    
    # Import calculation functions
    from app.services.pension_fund_service import (
        calculate_pension_amount,
        _compute_indexation_factor
    )
    
    # Test calculate_pension_amount
    print("\n=== Testing calculate_pension_amount ===")
    
    # Test calculated mode
    calc_fund = MockPensionFund(
        input_mode="calculated",
        balance=1000000.0,
        annuity_factor=200.0
    )
    calc_amount = calculate_pension_amount(calc_fund)
    print(f"Calculated pension amount: {calc_amount}")
    assert calc_amount == 5000.0, "Calculated pension amount should be 5000.0"
    
    # Test manual mode
    manual_fund = MockPensionFund(
        input_mode="manual",
        pension_amount=5000.0
    )
    manual_amount = calculate_pension_amount(manual_fund)
    print(f"Manual pension amount: {manual_amount}")
    assert manual_amount == 5000.0, "Manual pension amount should be 5000.0"
    
    # Test indexation factor calculation
    print("\n=== Testing indexation factor calculation ===")
    start_date = date.today() - timedelta(days=365)  # 1 year ago
    
    none_factor = _compute_indexation_factor("none", start_date, None)
    print(f"None indexation factor: {none_factor}")
    assert none_factor == 1.0, "None indexation factor should be 1.0"
    
    fixed_factor = _compute_indexation_factor("fixed", start_date, 0.02)
    print(f"Fixed indexation factor (2%): {fixed_factor}")
    assert abs(fixed_factor - 1.02) < 0.01, "Fixed indexation factor should be approximately 1.02"
    
    # Import more calculation functions
    from app.calculation.pensions import (
        calc_monthly_pension_from_capital,
        apply_indexation
    )
    
    # Test calc_monthly_pension_from_capital
    print("\n=== Testing calc_monthly_pension_from_capital ===")
    tax_params = MockTaxParams()
    pension = calc_monthly_pension_from_capital(1000000.0, tax_params)
    print(f"Monthly pension from capital: {pension}")
    assert pension == 5000.0, "Monthly pension from capital should be 5000.0"
    
    # Test apply_indexation
    print("\n=== Testing apply_indexation ===")
    
    # Test none indexation
    none_indexed = apply_indexation(5000.0, "none", start_date)
    print(f"None indexation: {none_indexed}")
    assert none_indexed == 5000.0, "None indexation should not change the amount"
    
    # Test fixed indexation
    fixed_indexed = apply_indexation(5000.0, "fixed", start_date, None, 0.02)
    print(f"Fixed indexation (2%): {fixed_indexed}")
    assert abs(fixed_indexed - 5100.0) < 1.0, "Fixed indexation should be approximately 5100.0"
    
    # Test CPI indexation
    cpi_indexed = apply_indexation(
        5000.0, "cpi", date(2023, 1, 1), date(2025, 1, 1), None, tax_params
    )
    print(f"CPI indexation: {cpi_indexed}")
    assert cpi_indexed == 5500.0, "CPI indexation should be 5500.0"
    
    print("\nAll pension calculation tests passed successfully!")

except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
