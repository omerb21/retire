"""
Simple script to verify app module can be imported
"""
try:
    import app
    print("Successfully imported app module")
    
    # Try importing specific modules
    from app.schemas import pension_fund
    print("Successfully imported pension_fund schema")
    
    from app.schemas import current_employer
    print("Successfully imported current_employer schema")
    
    print("All imports successful!")
except Exception as e:
    print(f"Error importing app: {e}")
    import traceback
    traceback.print_exc()
