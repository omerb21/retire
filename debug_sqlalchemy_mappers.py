"""
Debug script to identify SQLAlchemy mapper conflicts
"""
import sys
import traceback
from sqlalchemy.orm import clear_mappers

def test_basic_imports():
    """Test basic model imports"""
    try:
        print("=== Testing basic imports ===")
        clear_mappers()
        
        from app.database import Base
        print(f"✓ Base imported: {Base}")
        
        from app.models.client import Client
        print(f"✓ Client imported: {Client}")
        
        from app.models.current_employer import CurrentEmployer
        print(f"✓ CurrentEmployer imported: {CurrentEmployer}")
        
        print(f"Base metadata tables: {list(Base.metadata.tables.keys())}")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_model_creation():
    """Test creating model instances"""
    try:
        print("\n=== Testing model creation ===")
        clear_mappers()
        
        from app.models.client import Client
        from app.models.current_employer import CurrentEmployer
        
        print("Testing Client creation...")
        # Test Client creation - just create object without database
        client = Client()
        client.id_number = "123456789"
        client.id_number_raw = "123456789"
        client.full_name = "Test User"
        client.first_name = "Test"
        client.last_name = "User"
        from datetime import date
        client.birth_date = date(1980, 1, 1)
        print(f"✓ Client object created")
        
        print("Testing CurrentEmployer creation...")
        # Test CurrentEmployer creation - just create object without database
        employer = CurrentEmployer()
        employer.client_id = 1
        employer.employer_name = "Test Corp"
        employer.start_date = date(2020, 1, 1)
        print(f"✓ CurrentEmployer object created")
        
        return True
    except Exception as e:
        print(f"✗ Model creation failed: {e}")
        traceback.print_exc()
        return False

def test_database_setup():
    """Test database setup"""
    try:
        print("\n=== Testing database setup ===")
        from sqlalchemy import create_engine
        from app.database import setup_database
        
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        setup_database(engine)
        print("✓ Database setup successful")
        
        return True
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("SQLAlchemy Mapper Debug Script")
    print("=" * 40)
    
    tests = [
        test_basic_imports,
        test_model_creation,
        test_database_setup
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print(f"\n=== Summary ===")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("✓ All tests passed - SQLAlchemy setup is working")
    else:
        print("✗ Some tests failed - SQLAlchemy issues detected")

if __name__ == "__main__":
    main()
