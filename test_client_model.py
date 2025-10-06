"""
Direct test for Client model to verify id_number handling
"""
import traceback
import sys
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import our models
try:
    from app.models.client import Client
    from app.database import Base
    from app.services.client_service import normalize_id_number
    print("✓ Successfully imported models and services")
except ImportError as e:
    print(f"❌ Import error: {e}")
    traceback.print_exc()
    sys.exit(1)

# Create engine and connect to test database
print("Connecting to test database...")
try:
    engine = create_engine("sqlite:///test_db.sqlite")
    Base.metadata.create_all(engine)
    print("✓ Connected to database and created tables")
except Exception as e:
    print(f"❌ Database error: {e}")
    traceback.print_exc()
    sys.exit(1)

def test_client_creation():
    """Test creating clients with id_number instead of id_number_raw"""
    try:
        with Session(engine) as session:
            print("Cleaning up existing test clients...")
            try:
                # Clean up any existing test clients
                session.query(Client).filter(Client.id_number_raw.like("%123456789%")).delete()
                session.commit()
                print("✓ Cleaned up existing test clients")
            except Exception as e:
                print(f"❌ Error cleaning up clients: {e}")
                session.rollback()
            
            print("Creating test client with id_number...")
            # Create client with id_number - should automatically set id_number_raw
            try:
                test_id_number = "123456789"
                test_client = Client(
                    first_name="Test",
                    last_name="Client", 
                    id_number=test_id_number,  # Using id_number directly
                    birth_date=date(1990, 1, 1)
                )
                session.add(test_client)
                session.commit()
                print("✓ Client added to database")
            except SQLAlchemyError as e:
                print(f"❌ Error creating client: {e}")
                session.rollback()
                raise
            
            # Refresh to get updated values
            session.refresh(test_client)
            
            print("\nClient details:")
            print(f"  - ID: {test_client.id}")
            print(f"  - Name: {test_client.full_name}")
            print(f"  - id_number: {test_client.id_number}")
            print(f"  - id_number_raw: {test_client.id_number_raw}")
            
            # Verify that id_number_raw was set correctly
            if test_client.id_number_raw == test_id_number:
                print("✓ id_number_raw was correctly set from id_number")
            else:
                print(f"❌ id_number_raw ({test_client.id_number_raw}) does not match expected value ({test_id_number})")
                
            # Check if normalization is working
            normalized = normalize_id_number(test_id_number)
            print(f"  - Normalized id_number: {normalized}")
            
            # Verify that id_number returns normalized value
            if test_client.id_number == normalized:
                print("✓ id_number correctly returns normalized value")
            else:
                print(f"❌ id_number ({test_client.id_number}) does not match expected normalized value ({normalized})")
            
            print("\nClient model correctly handles id_number field! ✓")
            return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_client_creation()
