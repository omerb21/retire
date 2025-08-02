#!/usr/bin/env python3
"""
Script to reset alembic_version table and sync to new head
"""
from sqlalchemy import create_engine, text

def reset_alembic():
    """Reset alembic version table"""
    print("Resetting alembic state...")
    
    engine = create_engine("sqlite:///./retirement_planning.db", future=True)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        print("Dropped alembic_version table")
    
    print("Alembic state reset successfully")

if __name__ == "__main__":
    reset_alembic()
