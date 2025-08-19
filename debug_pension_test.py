"""
Debug script for pension fund calculation features
"""
import sys
import os
import traceback
from datetime import date, timedelta

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_imports():
    """Debug import issues"""
    print("=== Debugging imports ===")
    try:
        print("Importing app...")
        import app
        print("SUCCESS: app imported successfully")
    except Exception as e:
        print(f"FAILED: Failed to import app: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("Importing app.models...")
        import app.models
        print("SUCCESS: app.models imported successfully")
    except Exception as e:
        print(f"FAILED: Failed to import app.models: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("Importing database components...")
        from app.database import Base, engine
        print("SUCCESS: Database components imported successfully")
    except Exception as e:
        print(f"FAILED: Failed to import database components: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("Importing pension fund service...")
        from app.services.pension_fund_service import calculate_pension_amount
        print("SUCCESS: Pension fund service imported successfully")
    except Exception as e:
        print(f"FAILED: Failed to import pension fund service: {e}")
        traceback.print_exc()
        return False
    
    try:
        print("Importing pension calculation module...")
        from app.calculation.pensions import calc_monthly_pension_from_capital
        print("SUCCESS: Pension calculation module imported successfully")
    except Exception as e:
        print(f"FAILED: Failed to import pension calculation module: {e}")
        traceback.print_exc()
        return False
    
    return True

def debug_mock_calculations():
    """Debug pension calculations with mock objects"""
    print("\n=== Debugging mock calculations ===")
    
    try:
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
                }
        
        print("Importing calculation functions...")
        from app.services.pension_fund_service import calculate_pension_amount
        from app.calculation.pensions import calc_monthly_pension_from_capital
        
        print("Testing calculate_pension_amount...")
        # Test calculated mode
        calc_fund = MockPensionFund(
            input_mode="calculated",
            balance=1000000.0,
            annuity_factor=200.0
        )
        calc_amount = calculate_pension_amount(calc_fund)
        print(f"Calculated pension amount: {calc_amount}")
        
        # Test manual mode
        manual_fund = MockPensionFund(
            input_mode="manual",
            pension_amount=5000.0
        )
        manual_amount = calculate_pension_amount(manual_fund)
        print(f"Manual pension amount: {manual_amount}")
        
        print("Testing calc_monthly_pension_from_capital...")
        tax_params = MockTaxParams()
        pension = calc_monthly_pension_from_capital(1000000.0, tax_params)
        print(f"Monthly pension from capital: {pension}")
        
        print("SUCCESS: Mock calculations completed successfully")
        return True
    except Exception as e:
        print(f"FAILED: Mock calculations failed: {e}")
        traceback.print_exc()
        return False

def debug_database_connection():
    """Debug database connection"""
    print("\n=== Debugging database connection ===")
    try:
        print("Importing database components...")
        from app.database import SessionLocal
        
        print("Creating database session...")
        db = SessionLocal()
        
        print("Testing database connection...")
        result = db.execute("SELECT 1").scalar()
        print(f"Database connection test result: {result}")
        
        db.close()
        print("SUCCESS: Database connection successful")
        return True
    except Exception as e:
        print(f"FAILED: Database connection failed: {e}")
        traceback.print_exc()
        return False

def debug_model_access():
    """Debug model access"""
    print("\n=== Debugging model access ===")
    try:
        print("Importing models...")
        from app.models.client import Client
        from app.models.pension_fund import PensionFund
        from app.database import SessionLocal
        
        print("Creating database session...")
        db = SessionLocal()
        
        print("Querying clients...")
        clients = db.query(Client).limit(5).all()
        print(f"Found {len(clients)} clients")
        
        print("Querying pension funds...")
        funds = db.query(PensionFund).limit(5).all()
        print(f"Found {len(funds)} pension funds")
        
        db.close()
        print("SUCCESS: Model access successful")
        return True
    except Exception as e:
        print(f"FAILED: Model access failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main debug function"""
    print("=== PENSION CALCULATION DEBUG ===")
    
    # Debug imports
    if not debug_imports():
        print("FAILED: Import debugging failed, stopping further tests")
        return
    
    # Debug mock calculations
    if not debug_mock_calculations():
        print("FAILED: Mock calculation debugging failed, stopping further tests")
        return
    
    # Debug database connection
    if not debug_database_connection():
        print("FAILED: Database connection debugging failed, stopping further tests")
        return
    
    # Debug model access
    if not debug_model_access():
        print("FAILED: Model access debugging failed")
        return
    
    print("\n=== All debug tests passed successfully! ===")

if __name__ == "__main__":
    main()
