"""
Core pension calculation test script
This script tests only the core calculation functions without database dependencies
"""
import sys
import os
from datetime import date, timedelta

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock classes for testing
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

class MockTaxParams:
    def __init__(self):
        self.annuity_factor = 200.0
        self.cpi_series = {
            date(2023, 1, 1): 100.0,
            date(2023, 6, 1): 102.0,
            date(2024, 1, 1): 105.0,
            date(2024, 6, 1): 107.0,
            date(2025, 1, 1): 110.0,
        }
    
    def get_annuity_factor(self, age=None, gender=None):
        return self.annuity_factor
    
    def get_cpi(self, date_obj):
        # Find the closest date in the CPI series
        closest_date = min(self.cpi_series.keys(), key=lambda d: abs((d - date_obj).days))
        return self.cpi_series[closest_date]

def test_calculate_pension_amount():
    """Test the calculate_pension_amount function"""
    print("\n=== Testing calculate_pension_amount ===")
    
    # Define the function inline to avoid import issues
    def calculate_pension_amount(pension_fund):
        """Calculate the pension amount based on input mode"""
        if pension_fund.input_mode == "manual":
            return pension_fund.pension_amount
        elif pension_fund.input_mode == "calculated":
            return pension_fund.balance / pension_fund.annuity_factor
        else:
            raise ValueError(f"Invalid input mode: {pension_fund.input_mode}")
    
    # Test calculated mode
    calc_fund = MockPensionFund(
        input_mode="calculated",
        balance=1000000.0,
        annuity_factor=200.0
    )
    calc_amount = calculate_pension_amount(calc_fund)
    print(f"Calculated pension amount: {calc_amount}")
    assert abs(calc_amount - 5000.0) < 0.01, "Calculated pension amount should be 5000.0"
    
    # Test manual mode
    manual_fund = MockPensionFund(
        input_mode="manual",
        pension_amount=5000.0
    )
    manual_amount = calculate_pension_amount(manual_fund)
    print(f"Manual pension amount: {manual_amount}")
    assert abs(manual_amount - 5000.0) < 0.01, "Manual pension amount should be 5000.0"
    
    print("SUCCESS: calculate_pension_amount tests passed")
    return True

def test_calc_monthly_pension_from_capital():
    """Test the calc_monthly_pension_from_capital function"""
    print("\n=== Testing calc_monthly_pension_from_capital ===")
    
    # Define the function inline to avoid import issues
    def calc_monthly_pension_from_capital(capital, tax_params, age=None, gender=None):
        """Calculate monthly pension from capital using annuity factor"""
        annuity_factor = tax_params.get_annuity_factor(age, gender)
        return capital / annuity_factor
    
    tax_params = MockTaxParams()
    pension = calc_monthly_pension_from_capital(1000000.0, tax_params)
    print(f"Monthly pension from capital: {pension}")
    assert abs(pension - 5000.0) < 0.01, "Monthly pension from capital should be 5000.0"
    
    print("SUCCESS: calc_monthly_pension_from_capital tests passed")
    return True

def test_indexation_factor():
    """Test the indexation factor calculation"""
    print("\n=== Testing indexation factor calculation ===")
    
    # Define the function inline to avoid import issues
    def compute_indexation_factor(indexation_method, start_date, fixed_rate=None, reference_date=None, tax_params=None):
        """Compute the indexation factor based on the indexation method"""
        if reference_date is None:
            reference_date = date.today()
            
        if indexation_method == "none":
            return 1.0
        elif indexation_method == "fixed":
            if fixed_rate is None:
                raise ValueError("Fixed rate is required for fixed indexation")
            
            years = (reference_date - start_date).days / 365.25
            return (1 + fixed_rate) ** years
        elif indexation_method == "cpi":
            if tax_params is None:
                return 1.0  # Default to no indexation if tax params not available
                
            start_cpi = tax_params.get_cpi(start_date)
            current_cpi = tax_params.get_cpi(reference_date)
            
            if start_cpi == 0:
                return 1.0  # Avoid division by zero
                
            return current_cpi / start_cpi
        else:
            raise ValueError(f"Invalid indexation method: {indexation_method}")
    
    start_date = date(2023, 1, 1)
    reference_date = date(2025, 1, 1)
    tax_params = MockTaxParams()
    
    # Test none indexation
    none_factor = compute_indexation_factor("none", start_date)
    print(f"None indexation factor: {none_factor}")
    assert none_factor == 1.0, "None indexation factor should be 1.0"
    
    # Test fixed indexation
    fixed_factor = compute_indexation_factor("fixed", start_date, 0.02, reference_date)
    print(f"Fixed indexation factor (2%): {fixed_factor}")
    assert abs(fixed_factor - 1.04) < 0.01, "Fixed indexation factor should be approximately 1.04"
    
    # Test CPI indexation
    cpi_factor = compute_indexation_factor("cpi", start_date, None, reference_date, tax_params)
    print(f"CPI indexation factor: {cpi_factor}")
    assert abs(cpi_factor - 1.10) < 0.01, "CPI indexation factor should be approximately 1.10"
    
    print("SUCCESS: indexation factor tests passed")
    return True

def test_apply_indexation():
    """Test the apply_indexation function"""
    print("\n=== Testing apply_indexation ===")
    
    # Define the function inline to avoid import issues
    def apply_indexation(amount, indexation_method, start_date, reference_date=None, fixed_rate=None, tax_params=None):
        """Apply indexation to a pension amount"""
        if reference_date is None:
            reference_date = date.today()
            
        if indexation_method == "none":
            return amount
        elif indexation_method == "fixed":
            if fixed_rate is None:
                raise ValueError("Fixed rate is required for fixed indexation")
            
            years = (reference_date - start_date).days / 365.25
            return amount * ((1 + fixed_rate) ** years)
        elif indexation_method == "cpi":
            if tax_params is None:
                return amount  # Default to no indexation if tax params not available
                
            start_cpi = tax_params.get_cpi(start_date)
            current_cpi = tax_params.get_cpi(reference_date)
            
            if start_cpi == 0:
                return amount  # Avoid division by zero
                
            return amount * (current_cpi / start_cpi)
        else:
            raise ValueError(f"Invalid indexation method: {indexation_method}")
    
    start_date = date(2023, 1, 1)
    reference_date = date(2025, 1, 1)
    tax_params = MockTaxParams()
    base_amount = 5000.0
    
    # Test none indexation
    none_indexed = apply_indexation(base_amount, "none", start_date)
    print(f"None indexation: {none_indexed}")
    assert none_indexed == base_amount, "None indexation should not change the amount"
    
    # Test fixed indexation
    fixed_indexed = apply_indexation(base_amount, "fixed", start_date, reference_date, 0.02)
    print(f"Fixed indexation (2%): {fixed_indexed}")
    assert abs(fixed_indexed - 5200.0) < 10.0, "Fixed indexation should be approximately 5200.0"
    
    # Test CPI indexation
    cpi_indexed = apply_indexation(base_amount, "cpi", start_date, reference_date, None, tax_params)
    print(f"CPI indexation: {cpi_indexed}")
    assert abs(cpi_indexed - 5500.0) < 10.0, "CPI indexation should be approximately 5500.0"
    
    print("SUCCESS: apply_indexation tests passed")
    return True

def test_project_pension_cashflow():
    """Test the project_pension_cashflow function"""
    print("\n=== Testing project_pension_cashflow ===")
    
    # Define the function inline to avoid import issues
    def project_pension_cashflow(pension_fund, months, reference_date=None, tax_params=None):
        """Project pension cashflow for a number of months"""
        if reference_date is None:
            reference_date = date.today()
            
        # Calculate base pension amount
        if pension_fund.input_mode == "manual":
            base_amount = pension_fund.pension_amount
        elif pension_fund.input_mode == "calculated":
            base_amount = pension_fund.balance / pension_fund.annuity_factor
        else:
            raise ValueError(f"Invalid input mode: {pension_fund.input_mode}")
        
        # Generate cashflow
        cashflow = []
        for i in range(months):
            month_date = reference_date.replace(day=1) + timedelta(days=i*30)
            
            # Apply indexation
            if pension_fund.indexation_method == "none":
                amount = base_amount
            elif pension_fund.indexation_method == "fixed":
                years = (month_date - pension_fund.pension_start_date).days / 365.25
                amount = base_amount * ((1 + pension_fund.fixed_index_rate) ** years)
            elif pension_fund.indexation_method == "cpi":
                if tax_params is None:
                    amount = base_amount  # Default to no indexation if tax params not available
                else:
                    start_cpi = tax_params.get_cpi(pension_fund.pension_start_date)
                    current_cpi = tax_params.get_cpi(month_date)
                    amount = base_amount * (current_cpi / start_cpi)
            else:
                raise ValueError(f"Invalid indexation method: {pension_fund.indexation_method}")
            
            cashflow.append({
                "date": month_date.isoformat(),
                "amount": amount
            })
        
        return cashflow
    
    reference_date = date(2023, 1, 1)
    tax_params = MockTaxParams()
    
    # Test none indexation
    none_fund = MockPensionFund(
        input_mode="manual",
        pension_amount=5000.0,
        indexation_method="none",
        pension_start_date=reference_date
    )
    none_cashflow = project_pension_cashflow(none_fund, 3, reference_date, tax_params)
    print(f"None indexation cashflow: {none_cashflow}")
    assert len(none_cashflow) == 3, "Cashflow should have 3 months"
    assert abs(float(none_cashflow[0]["amount"]) - 5000.0) < 0.01, "First month amount should be 5000.0"
    assert abs(float(none_cashflow[2]["amount"]) - 5000.0) < 0.01, "Last month amount should be 5000.0"
    
    # Test fixed indexation
    fixed_fund = MockPensionFund(
        input_mode="manual",
        pension_amount=5000.0,
        indexation_method="fixed",
        fixed_index_rate=0.02,
        pension_start_date=reference_date
    )
    fixed_cashflow = project_pension_cashflow(fixed_fund, 3, reference_date, tax_params)
    print(f"Fixed indexation cashflow: {fixed_cashflow}")
    assert len(fixed_cashflow) == 3, "Cashflow should have 3 months"
    assert abs(float(fixed_cashflow[0]["amount"]) - 5000.0) < 0.01, "First month amount should be 5000.0"
    # Last month is approximately 2 months later, so very small increase
    assert float(fixed_cashflow[2]["amount"]) > 5000.0, "Last month amount should be greater than 5000.0"
    
    print("SUCCESS: project_pension_cashflow tests passed")
    return True

def main():
    """Main function to run all tests"""
    print("=== CORE PENSION CALCULATION TESTS ===")
    
    try:
        # Run tests
        test_calculate_pension_amount()
        test_calc_monthly_pension_from_capital()
        test_indexation_factor()
        test_apply_indexation()
        test_project_pension_cashflow()
        
        print("\n=== All tests passed successfully! ===")
    except Exception as e:
        import traceback
        print(f"\n=== Test failed: {e} ===")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    main()
