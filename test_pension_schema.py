"""
Test script to verify Pydantic schema changes
"""
import sys
from datetime import date

# Try importing the pension fund schemas
try:
    from app.schemas.pension_fund import PensionFundBase, PensionFundCreate, PensionFundOut
    print("✓ Successfully imported pension_fund schemas")
    
    # Create a test instance
    test_fund = PensionFundBase(
        fund_name="Test Pension Fund",
        input_mode="calculated",
        indexation_method="none"
    )
    print(f"✓ Created test pension fund: {test_fund.model_dump()}")
    
    # Test PensionFundCreate
    test_fund_create = PensionFundCreate(
        fund_name="Test Pension Fund",
        input_mode="calculated",
        indexation_method="none",
        client_id=1
    )
    print(f"✓ Created test pension fund create: {test_fund_create.model_dump()}")
    
    # Test PensionFundOut
    test_fund_out = PensionFundOut(
        id=1,
        client_id=1,
        fund_name="Test Pension Fund",
        input_mode="calculated",
        indexation_method="none",
        indexed_pension_amount=1000.0
    )
    print(f"✓ Created test pension fund out: {test_fund_out.model_dump()}")
    
except Exception as e:
    print(f"✗ Error with pension_fund schemas: {e}")
    import traceback
    traceback.print_exc()

# Try importing the current employer schemas
try:
    from app.schemas.current_employer import CurrentEmployerOut, EmployerGrantOut
    print("✓ Successfully imported current_employer schemas")
    
    # Test model_config is working
    print(f"✓ CurrentEmployerOut model_config: {CurrentEmployerOut.model_config}")
    print(f"✓ EmployerGrantOut model_config: {EmployerGrantOut.model_config}")
    
except Exception as e:
    print(f"✗ Error with current_employer schemas: {e}")
    import traceback
    traceback.print_exc()

# Try importing the client schemas
try:
    from app.schemas.client import ClientResponse
    print("✓ Successfully imported client schemas")
    
    # Test model_config is working
    print(f"✓ ClientResponse model_config: {ClientResponse.model_config}")
    
except Exception as e:
    print(f"✗ Error with client schemas: {e}")
    import traceback
    traceback.print_exc()

print("\nAll tests completed!")
