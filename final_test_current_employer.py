"""
Final comprehensive test for the current employer endpoint with detailed output
Uses PowerShell direct output to ensure we can see all messages
"""
import os
import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from datetime import date
import traceback

# Import the necessary modules from our app
from app.main import app
from app.database import Base, get_db
from app.models.client import Client
from app.models.current_employer import CurrentEmployer

# Make sure output is flushed immediately
sys.stdout.reconfigure(line_buffering=True)

def print_with_flush(message):
    """Print message and flush immediately to ensure output in PowerShell"""
    print(message, flush=True)
    
# Set up a dedicated test database with a unique file
TEST_DB_FILE = "final_test.db"
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)
    
print_with_flush("*" * 80)
print_with_flush("STARTING FINAL CURRENT EMPLOYER TEST")
print_with_flush("*" * 80)

DB_URL = f"sqlite:///{TEST_DB_FILE}"
print_with_flush(f"Creating engine with URL: {DB_URL}")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
print_with_flush("Creating session factory")
TestSessionLocal = sessionmaker(autoflush=True, expire_on_commit=False, bind=engine)

# Create all tables
print_with_flush("Creating database tables")
Base.metadata.create_all(bind=engine)

# Override the FastAPI dependency
def override_get_db():
    db = TestSessionLocal()
    session_id = id(db)
    print_with_flush(f"Creating API session: {session_id}")
    try:
        yield db
    finally:
        print_with_flush(f"Closed API session: {session_id}")
        db.close()

# Apply the override
print_with_flush("Overriding get_db dependency")
app.dependency_overrides[get_db] = override_get_db

# Create test client
print_with_flush("Creating FastAPI TestClient")
test_client = TestClient(app)

def ensure_clean_db():
    """Make sure we start with a clean database"""
    print_with_flush("\nCleaning database...")
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            print_with_flush(f"  - Clearing table: {table.name}")
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()
    print_with_flush("Database cleaned!")

def test_current_employer():
    """Test the current employer endpoint"""
    # Start with a clean database
    ensure_clean_db()
    
    try:
        # Step 1: Create a client
        print_with_flush("\n\n=== Step 1: Creating test client ===")
        db = TestSessionLocal()
        print_with_flush(f"Using session ID: {id(db)}")
        
        client = Client(
            id_number_raw="final_test_123",
            id_number="final_test_123",
            full_name="Final Test Client",
            birth_date=date(1990, 1, 1),
            is_active=True
        )
        print_with_flush("Adding client to session")
        db.add(client)
        print_with_flush("Committing client to database")
        db.commit()
        print_with_flush("Refreshing client object")
        db.refresh(client)
        client_id = client.id
        print_with_flush(f"Created client ID: {client_id}")
        print_with_flush("Closing client creation session")
        db.close()
        
        # Step 2: Verify the client exists in the database with a new session
        print_with_flush("\n\n=== Step 2: Verifying client exists with a new session ===")
        db = TestSessionLocal()
        print_with_flush(f"Using new session ID: {id(db)}")
        print_with_flush(f"Looking for client with ID: {client_id}")
        
        # Try different methods to find the client
        print_with_flush("Trying with db.get()")
        found = db.get(Client, client_id)
        if found:
            print_with_flush(f"✅ Client found with db.get(): ID={found.id}, Name={found.full_name}")
        else:
            print_with_flush("❌ Client NOT found with db.get()")
            print_with_flush("Trying with query().filter().first()")
            found = db.query(Client).filter(Client.id == client_id).first()
            if found:
                print_with_flush(f"✅ Client found with query: ID={found.id}, Name={found.full_name}")
            else:
                print_with_flush("❌ Client NOT found with query either")
                print_with_flush("Trying with scalar(select())")
                found = db.scalar(select(Client).where(Client.id == client_id))
                if found:
                    print_with_flush(f"✅ Client found with scalar: ID={found.id}, Name={found.full_name}")
                else:
                    print_with_flush("❌ Client NOT found with any method!")
                    print_with_flush("Test will fail - cannot proceed")
                    return False
        
        # Step 3: Call the API endpoint
        print_with_flush("\n\n=== Step 3: Calling API endpoint ===")
        endpoint = f"/api/v1/clients/{client_id}/current-employer"
        print_with_flush(f"GET {endpoint}")
        response = test_client.get(endpoint)
        
        # Step 4: Validate the response
        print_with_flush("\n\n=== Step 4: Validating response ===")
        print_with_flush(f"Response status code: {response.status_code}")
        print_with_flush(f"Response body: {response.text}")
        
        expected_status = 404
        expected_error = "אין מעסיק נוכחי רשום ללקוח"
        
        if response.status_code == expected_status:
            try:
                response_json = response.json()
                print_with_flush(f"Parsed response JSON: {response_json}")
                
                if "detail" in response_json and "error" in response_json["detail"]:
                    actual_error = response_json["detail"]["error"]
                    print_with_flush(f"Extracted error message: '{actual_error}'")
                    print_with_flush(f"Expected error message: '{expected_error}'")
                    
                    if actual_error == expected_error:
                        print_with_flush("\n\n✅ SUCCESS: Got expected error message!")
                        return True
                    else:
                        print_with_flush("\n\n❌ FAILED: Got wrong error message.")
                        print_with_flush(f"  Expected: '{expected_error}'")
                        print_with_flush(f"  Actual: '{actual_error}'")
                        return False
                else:
                    print_with_flush("\n\n❌ FAILED: Response JSON doesn't have expected structure")
                    return False
            except Exception as e:
                print_with_flush(f"\n\n❌ FAILED: Couldn't parse response JSON: {e}")
                return False
        else:
            print_with_flush(f"\n\n❌ FAILED: Got status code {response.status_code} instead of {expected_status}")
            return False
            
    except Exception as e:
        print_with_flush(f"\n\n❌ ERROR: {e}")
        print_with_flush("Detailed traceback:")
        traceback.print_exc()
        return False
    finally:
        # Make sure to close any open sessions
        try:
            if 'db' in locals() and db:
                print_with_flush("Closing final database session")
                db.close()
        except:
            pass

if __name__ == "__main__":
    print_with_flush("\n\n============================================")
    print_with_flush("=== RUNNING FINAL TEST OF CURRENT EMPLOYER ENDPOINT ===")
    print_with_flush("============================================")
    
    try:
        success = test_current_employer()
        
        if success:
            print_with_flush("\n\n============================================")
            print_with_flush("=== 🎉 TEST PASSED! ALL FIXES WORKED! 🎉 ===")
            print_with_flush("============================================")
            sys.exit(0)
        else:
            print_with_flush("\n\n============================================")
            print_with_flush("=== ❌ TEST FAILED - ISSUE REMAINS ❌ ===")
            print_with_flush("============================================")
            sys.exit(1)
    except Exception as e:
        print_with_flush(f"\n\nUnhandled exception: {str(e)}")
        print_with_flush("Detailed traceback:")
        traceback.print_exc()
        sys.exit(2)
