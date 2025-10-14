from app.database import SessionLocal
from app.models.client import Client
from app.utils.default_client import ensure_default_client

def reset_default_client():
    db = SessionLocal()
    try:
        # Delete existing client
        client = db.query(Client).filter(Client.id_number == '123456789').first()
        if client:
            print(f"Deleting existing client: {client.full_name}")
            db.delete(client)
            db.commit()
            print('Client deleted')
        else:
            print('Client not found')
            
        # Create new default client
        ensure_default_client()
        
    finally:
        db.close()

if __name__ == "__main__":
    reset_default_client()
