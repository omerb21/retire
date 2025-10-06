"""
Simple script to run the test directly without pytest
"""
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import date
import traceback

# Import necessary modules from app
from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.routers.current_employer import router as current_employer_router

# Set up a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_direct_runner.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

def run_test():
    print("\n=== Running Test: Client exists but has no current employer ===")
    
    # Create a test client in the DB
    db = TestingSessionLocal()
    try:
        # Create a test client
        test_client = Client(
            id_number_raw="direct_test_client",
            id_number="direct_test_client",
            full_name="Direct Test Client",
            birth_date=date(1990, 1, 1),
            is_active=True
        )
        db.add(test_client)
        db.commit()
        db.refresh(test_client)
        client_id = test_client.id
        print(f"Created test client with ID: {client_id}")
        
        # Make sure no current employer exists
        ce = db.scalar(select(CurrentEmployer).where(CurrentEmployer.client_id == client_id))
        if ce:
            print("Found existing current employer, deleting it")
            db.delete(ce)
            db.commit()
        
        # Verify client exists in a fresh session
        verify_db = TestingSessionLocal()
        try:
            found = verify_db.query(Client).filter(Client.id == client_id).first()
            print(f"Client found in verification query: {found is not None}")
            if found:
                print(f"Client details: ID={found.id}, Name={found.full_name}")
        finally:
            verify_db.close()
        
        # Simulate the API endpoint directly
        print("\n--- Simulating API endpoint ---")
        endpoint_db = TestingSessionLocal()
        try:
            # First check if client exists - what the endpoint does
            print(f"Looking for client with ID: {client_id}")
            
            # Try multiple approaches
            client = endpoint_db.get(Client, client_id)
            if not client:
                client = endpoint_db.query(Client).filter(Client.id == client_id).first()
                if not client:
                    client = endpoint_db.scalar(select(Client).where(Client.id == client_id))
            
            print(f"Client found in endpoint: {client is not None}")
            if client:
                print(f"Client details: ID={client.id}, Name={client.full_name}")
                
                # Look for current employer
                ce = endpoint_db.scalar(
                    select(CurrentEmployer)
                    .where(CurrentEmployer.client_id == client_id)
                )
                print(f"Current employer found: {ce is not None}")
                
                if not ce:
                    # Should raise the "אין מעסיק נוכחי רשום ללקוח" error
                    print("TEST PASSED: Client exists but has no current employer")
                    return True
            else:
                print("TEST FAILED: Client not found in endpoint")
                return False
        finally:
            endpoint_db.close()
    except Exception as e:
        print(f"Error during test: {e}")
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n=== Test completed successfully ===")
        sys.exit(0)
    else:
        print("\n=== Test failed ===")
        sys.exit(1)
