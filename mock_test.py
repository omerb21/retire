"""
Simple mock test for SQLAlchemy models that avoids import conflicts
"""
import os
import sys
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers

def test_mock_client():
    """Test client model with mock data"""
    # Add current directory to path
    sys.path.insert(0, '.')
    
    # Clear any existing mappers
    clear_mappers()
    
    # Import Base from app.database
    from app.database import Base
    
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    try:
        # Create engine with proper connect_args
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        # Import models after clearing mappers
        from app.models.client import Client
        from app.models.current_employer import CurrentEmployer
        from datetime import date
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Test Client creation
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
        
        # Test CurrentEmployer creation
        employer = CurrentEmployer()
        employer.client_id = client.id
        employer.employer_name = "Test Corp"
        employer.start_date = date(2020, 1, 1)
        
        session.add(employer)
        session.commit()
        print(f"✓ CurrentEmployer created with ID: {employer.id}")
        
        # Test query
        found_client = session.query(Client).filter(Client.id == client.id).first()
        print(f"✓ Client query successful: {found_client.full_name}")
        
        # Close session
        session.close()
        
        print("✓ All tests passed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
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
    success = test_mock_client()
    exit(0 if success else 1)
