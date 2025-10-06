"""
Test script to verify the PensionFund model and SQLAlchemy table references
"""
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Importing app modules...")
    import app.models  # This should load all models including PensionFund
    from app.database import Base, engine
    from app.models.client import Client
    from app.models.pension_fund import PensionFund
    
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Creating session...")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    print("Creating test client...")
    test_client = Client(
        id_number_raw="123456789",
        id_number="123456789",
        full_name="Test Client",
        birth_date="1980-01-01"
    )
    db.add(test_client)
    db.commit()
    db.refresh(test_client)
    print(f"Created test client with ID: {test_client.id}")
    
    print("Creating test pension fund...")
    test_fund = PensionFund(
        client_id=test_client.id,
        fund_name="Test Pension Fund",
        input_mode="calculated",
        indexation_method="none"
    )
    db.add(test_fund)
    db.commit()
    db.refresh(test_fund)
    print(f"Created test pension fund with ID: {test_fund.id}")
    
    print("Testing relationship...")
    client_with_funds = db.query(Client).filter(Client.id == test_client.id).first()
    print(f"Client pension funds: {client_with_funds.pension_funds}")
    
    fund_with_client = db.query(PensionFund).filter(PensionFund.id == test_fund.id).first()
    print(f"Fund client: {fund_with_client.client}")
    
    print("Cleaning up test data...")
    db.delete(test_client)  # Should cascade delete the pension fund
    db.commit()
    
    print("All tests passed successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        db.close()
    except:
        pass
