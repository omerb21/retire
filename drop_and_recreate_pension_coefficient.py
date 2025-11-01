import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models import PensionFundCoefficient

def drop_and_recreate_table():
    print("Dropping and recreating pension_fund_coefficient table...")
    
    try:
        # Drop the table if it exists
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS pension_fund_coefficient"))
            conn.commit()
        print("✓ Dropped existing pension_fund_coefficient table")
        
        # Recreate all tables
        print("Recreating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Recreated database tables")
        
        # Add initial data
        session = sessionmaker(bind=engine)()
        try:
            print("Adding initial pension fund coefficient data...")
            # Add some sample data
            coefficients = [
                PensionFundCoefficient(
                    sex='male',
                    retirement_age=67,
                    survivors_option='standard',
                    base_coefficient=200.0,
                    adjust_percent=0.0,
                    fund_name='default',
                    notes='Default coefficient for male at retirement age 67'
                ),
                PensionFundCoefficient(
                    sex='female',
                    retirement_age=62,
                    survivors_option='standard',
                    base_coefficient=220.0,
                    adjust_percent=0.0,
                    fund_name='default',
                    notes='Default coefficient for female at retirement age 62'
                )
            ]
            session.add_all(coefficients)
            session.commit()
            print(f"✓ Added {len(coefficients)} initial coefficients")
            
            # Verify the data was added
            count = session.query(PensionFundCoefficient).count()
            print(f"✓ Verified {count} coefficients in database")
            
        except Exception as e:
            session.rollback()
            print(f"Error adding initial data: {e}")
            raise
        finally:
            session.close()
            
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    
    print("\nTable recreation completed successfully!")
    return True

if __name__ == "__main__":
    print("Starting pension fund coefficient table recreation...\n")
    success = drop_and_recreate_table()
    sys.exit(0 if success else 1)
