from datetime import date
from app.services.tax_calculator import TaxCalculator
from app.schemas.tax_schemas import TaxCalculationInput, PersonalDetails

def test_tax_calculation_2026():
    """Test tax calculation for 2026"""
    print("\n" + "="*80)
    print("Testing 2026 Tax Calculation")
    print("="*80)
    
    # Create a calculator for 2026
    calculator = TaxCalculator(tax_year=2026)
    
    # Client 4 details (from the screenshot)
    personal_details = PersonalDetails(
        birth_date=date(1960, 5, 15),  # Assuming age ~64
        marital_status="married",
        num_children=0
    )
    
    # Input data based on the screenshot
    input_data = TaxCalculationInput(
        tax_year=2026,
        personal_details=personal_details,
        pension_income=120000,  # 10,000 per month
        pension_months_in_year=12,
        business_income=0,
        other_income=0
    )
    
    # Calculate tax
    result = calculator.calculate_comprehensive_tax(input_data)
    
    # Print results
    print(f"\nIncome: {result.total_income:,.2f}")
    print(f"Taxable Income: {result.taxable_income:,.2f}")
    print(f"Income Tax: {result.income_tax:,.2f}")
    print(f"National Insurance: {result.national_insurance:,.2f}")
    print(f"Health Tax: {result.health_tax:,.2f}")
    print(f"Total Tax: {result.net_tax:,.2f}")
    print(f"Net Income: {result.net_income:,.2f}")
    print(f"Effective Tax Rate: {result.effective_tax_rate:.2f}%")
    
    # Verify tax is not more than income
    assert result.net_tax < result.total_income, "Tax cannot be more than income!"
    
    # Verify tax is reasonable (less than 50% of income)
    assert result.net_tax < result.total_income * 0.5, "Tax is too high!"
    
    print("\n✅ Test passed - Tax calculation is reasonable")

if __name__ == "__main__":
    test_tax_calculation_2026()
