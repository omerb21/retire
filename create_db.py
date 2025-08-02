#!/usr/bin/env python3
"""
Script to create database schema with all models
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import engine, Base
from app.models import *  # Import all models

def create_database():
    """Create all database tables"""
    print("Creating database tables...")
    
    # Drop all existing tables
    Base.metadata.drop_all(bind=engine)
    print("Dropped existing tables")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Created all tables successfully")
    
    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Created tables: {', '.join(tables)}")

if __name__ == "__main__":
    create_database()
