"""
Database reset script - recreates all tables from models
"""
import os
import sys
from app.database import engine, Base
from app.models import client, employer, employment, current_employer, employer_grant

def reset_database():
    """Drop all tables and recreate them"""
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Database reset complete!")

if __name__ == "__main__":
    # Confirm before proceeding
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        reset_database()
    else:
        confirm = input("This will delete all data in the database. Are you sure? (y/N): ")
        if confirm.lower() == 'y':
            reset_database()
        else:
            print("Operation cancelled.")
