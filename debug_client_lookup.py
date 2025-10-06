"""
Debug script to verify client lookup across sessions
"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import os
from app.models.client import Client
from app.models.current_employer import CurrentEmployer
from app.database import Base

# Create a database
db_path = os.path.join(os.path.dirname(__file__), "test_debug.db")
engine = create_engine(f"sqlite:///{db_path}", echo=True)
Base.metadata.create_all(engine)

# Create a session
Session = sessionmaker(bind=engine)

# Create a client in one session
with Session() as session1:
    print("\n--- Creating client in session1 ---")
    client = Client(
        id_number_raw="debug123",
        id_number="debug123",
        full_name="Debug Client",
        birth_date="1980-01-01",
        is_active=True
    )
    session1.add(client)
    session1.commit()
    client_id = client.id
    print(f"Created client with ID: {client_id}")

# Check if client exists in another session
with Session() as session2:
    print("\n--- Looking up client in session2 ---")
    found = session2.query(Client).filter(Client.id == client_id).first()
    print(f"Client found: {found is not None}")
    if found:
        print(f"Client details: ID={found.id}, Name={found.full_name}")

# Try another query method
with Session() as session3:
    print("\n--- Alternative lookup in session3 ---")
    found = session3.get(Client, client_id)
    print(f"Client found with get(): {found is not None}")
    if found:
        print(f"Client details: ID={found.id}, Name={found.full_name}")

# Verify CurrentEmployer relationship
with Session() as session4:
    print("\n--- Testing CurrentEmployer relationship in session4 ---")
    # First ensure client exists
    client = session4.query(Client).filter(Client.id == client_id).first()
    assert client is not None
    
    # Check if has current employer
    ce = session4.scalar(
        select(CurrentEmployer)
        .where(CurrentEmployer.client_id == client_id)
    )
    print(f"Has current employer: {ce is not None}")
    
    # Now verify our endpoint logic works
    if not ce:
        print("Would return: 'אין מעסיק נוכחי רשום ללקוח'")

print("\nDebug complete. Check output for insights.")
