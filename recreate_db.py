import os
from app.database import engine, Base
import app.models  # Import all models to ensure they are registered

def recreate_database():
    # Get the database path
    db_path = 'app.db'
    
    # Delete the database file if it exists
    if os.path.exists(db_path):
        print(f"Deleting existing database: {db_path}")
        os.remove(db_path)
        print("Database deleted")
    
    # Create all tables
    print("Creating new database schema")
    Base.metadata.create_all(bind=engine)
    print("Database schema created")
    
    # Create default client
    from app.utils.default_client import ensure_default_client
    ensure_default_client()
    print("Default client created")

if __name__ == "__main__":
    recreate_database()
