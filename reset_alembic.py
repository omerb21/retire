#!/usr/bin/env python3
"""
Script to reset alembic state
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database import engine
from sqlalchemy import text

def reset_alembic():
    """Reset alembic version table"""
    print("Resetting alembic state...")
    
    with engine.connect() as conn:
        # Drop alembic_version table if it exists
        try:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
            conn.commit()
            print("Dropped alembic_version table")
        except Exception as e:
            print(f"Error dropping alembic_version table: {e}")
    
    print("Alembic state reset successfully")

if __name__ == "__main__":
    reset_alembic()
