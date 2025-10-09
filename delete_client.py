from app.database import SessionLocal
from app.models.client import Client

def delete_client():
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id_number == '123456789').first()
        if client:
            db.delete(client)
            db.commit()
            print('Client deleted')
        else:
            print('Client not found')
    finally:
        db.close()

if __name__ == "__main__":
    delete_client()
