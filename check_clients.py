#!/usr/bin/env python3
"""
Script to check clients in database
"""
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal
from app.models import Client

def check_clients():
    """Check clients in database"""
    print("Checking clients in database...")
    
    db = SessionLocal()
    try:
        clients = db.query(Client).all()
        print(f"Found {len(clients)} clients:")
        
        for client in clients:
            print(f"  ID: {client.id}, Name: {client.full_name}, Active: {client.is_active}")
            
        if not clients:
            print("No clients found. Creating a test client...")
            from datetime import date
            test_client = Client(
                id_number_raw="123456789",
                id_number="123456789",
                full_name="ישראל ישראלי",
                first_name="ישראל",
                last_name="ישראלי",
                birth_date=date(1980, 1, 1),
                is_active=True
            )
            db.add(test_client)
            db.commit()
            print(f"Created test client with ID: {test_client.id}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_clients()
