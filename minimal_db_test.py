"""
Minimal reproducer for DB-based tests without SQLAlchemy conflicts
"""
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers
from app.database import Base, setup_database

def test_minimal_db_operations():
    """Test basic database operations"""
    print("=== Minimal DB Test ===")
    
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        # Create engine and setup database
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        setup_database(engine)
        
        # Create session
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        # Import models after database setup
        from app.models.client import Client
        from app.models.current_employer import CurrentEmployer
        from datetime import date
        
        # Test Client creation and save
        client = Client()
        client.id_number = "123456789"
        client.id_number_raw = "123456789"
        client.full_name = "Test User"
        client.first_name = "Test"
        client.last_name = "User"
        client.birth_date = date(1980, 1, 1)
        client.gender = "male"
        client.marital_status = "single"
        client.self_employed = False
        client.current_employer_exists = True
        client.is_active = True
        
        session.add(client)
        session.commit()
        print(f"✓ Client created with ID: {client.id}")
        
        # Test CurrentEmployer creation and save
        employer = CurrentEmployer()
        employer.client_id = client.id
        employer.employer_name = "Test Corp"
        employer.start_date = date(2020, 1, 1)
        
        session.add(employer)
        session.commit()
        print(f"✓ CurrentEmployer created with ID: {employer.id}")
        
        # Test query operations
        found_client = session.query(Client).filter(Client.id == client.id).first()
        print(f"✓ Client query successful: {found_client.full_name}")
        
        found_employer = session.query(CurrentEmployer).filter(CurrentEmployer.client_id == client.id).first()
        print(f"✓ CurrentEmployer query successful: {found_employer.employer_name}")
        
        session.close()
        engine.dispose()
        
        print("✓ All database operations successful")
        return True
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass

if __name__ == "__main__":
    success = test_minimal_db_operations()
    exit(0 if success else 1)
