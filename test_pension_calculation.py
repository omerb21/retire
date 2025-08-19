"""
Test script to verify the pension fund calculation features
"""
import sys
import os
from datetime import date, timedelta
import traceback

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing app modules...")
    import app.models
    from app.database import Base, engine
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
    from app.services.pension_fund_service import (
        calculate_pension_amount,
        compute_and_apply_indexation,
        _compute_indexation_factor
    )
    from app.calculation.pensions import (
        calc_monthly_pension_from_capital,
        calc_pension_from_fund,
        apply_indexation,
        project_pension_cashflow
    )
    from app.providers.tax_params import TaxParamsProvider
    from sqlalchemy.orm import sessionmaker
    
    print("Creating database session...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Create test client
    print("Setting up test data...")
    test_client = db.query(Client).filter(Client.id_number == "999999999").first()
    if not test_client:
        test_client = Client(
            id_number_raw="999999999",
            id_number="999999999",
            full_name="Test Pension User",
            birth_date="1970-01-01",
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
    print(f"Test client ID: {test_client.id}")
    
    # Create test pension funds
    funds = db.query(PensionFund).filter(PensionFund.client_id == test_client.id).all()
    if not funds:
        # Create calculated fund
        calc_fund = PensionFund(
            client_id=test_client.id,
            fund_name="Test Calculated Fund",
            fund_type="Pension",
            input_mode="calculated",
            balance=1000000.0,
            annuity_factor=200.0,
            pension_start_date=date.today() - timedelta(days=365),
            indexation_method="none",
            remarks="Test calculated fund"
        )
        db.add(calc_fund)
        
        # Create manual fund with fixed indexation
        manual_fund = PensionFund(
            client_id=test_client.id,
            fund_name="Test Manual Fund",
            fund_type="Pension",
            input_mode="manual",
            pension_amount=5000.0,
            pension_start_date=date.today() - timedelta(days=365),
            indexation_method="fixed",
            fixed_index_rate=0.02,
            remarks="Test manual fund"
        )
        db.add(manual_fund)
        
        db.commit()
        db.refresh(calc_fund)
        db.refresh(manual_fund)
        funds = [calc_fund, manual_fund]
    
    print(f"Found {len(funds)} pension funds")
    
    # Test pension calculation functions
    print("\n=== Testing pension calculation functions ===")
    
    # Test calculate_pension_amount
    for fund in funds:
        pension_amount = calculate_pension_amount(fund)
        print(f"Fund '{fund.fund_name}' pension amount: {pension_amount}")
    
    # Test indexation factor calculation
    print("\n=== Testing indexation factor calculation ===")
    start_date = date.today() - timedelta(days=365)  # 1 year ago
    
    none_factor = _compute_indexation_factor("none", start_date, None)
    print(f"None indexation factor: {none_factor}")
    
    fixed_factor = _compute_indexation_factor("fixed", start_date, 0.02)
    print(f"Fixed indexation factor (2%): {fixed_factor}")
    
    # Test compute_and_apply_indexation
    print("\n=== Testing compute_and_apply_indexation ===")
    for fund in funds:
        base, indexed = compute_and_apply_indexation(fund)
        print(f"Fund '{fund.fund_name}': Base={base}, Indexed={indexed}")
    
    # Test pension cashflow projection
    print("\n=== Testing pension cashflow projection ===")
    for fund in funds:
        cashflow = project_pension_cashflow(fund, 3)
        print(f"Fund '{fund.fund_name}' cashflow ({len(cashflow)} months):")
        for cf in cashflow:
            print(f"  {cf['date']}: {cf['amount']}")
    
    print("\nAll pension calculation tests completed successfully!")

except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
finally:
    try:
        db.close()
    except:
        pass
