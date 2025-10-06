"""
Simple script to test if Pydantic schemas can be imported without errors
"""
import sys
print(f"Python version: {sys.version}")

try:
    from app.schemas.pension_fund import PensionFundBase, PensionFundCreate, PensionFundOut
    print("Successfully imported pension_fund schemas")
    
    # Create a test instance to verify schema works
    test_fund = PensionFundBase(
        fund_name="Test Fund",
        input_mode="calculated",
        indexation_method="none"
    )
    print(f"Created test fund: {test_fund}")
    
    from app.schemas.current_employer import CurrentEmployerOut, EmployerGrantOut
    print("Successfully imported current_employer schemas")
    
    print("All imports successful!")
except Exception as e:
    print(f"Error importing schemas: {e}")
    import traceback
    traceback.print_exc()
