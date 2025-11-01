import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine
from app.models import PensionFundCoefficient

def run_pension_coefficient_migration():
    print("Starting pension fund coefficient migration...")
    
    # Create all tables defined in Base
    try:
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created successfully")
        
        # Check if the table was created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='pension_fund_coefficient'
            """))
            table_exists = result.fetchone() is not None
            
            if table_exists:
                print("✓ pension_fund_coefficient table exists")
                
                # Add some initial data
                session = sessionmaker(bind=engine)()
                try:
                    # Check if we already have data
                    count = session.query(PensionFundCoefficient).count()
                    if count == 0:
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
                    else:
                        print(f"✓ Found {count} existing coefficients")
                except Exception as e:
                    session.rollback()
                    print(f"Error adding initial data: {e}")
                finally:
                    session.close()
            else:
                print("❌ Error: pension_fund_coefficient table was not created")
                return False
                
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    
    print("\nMigration completed successfully!")
    return True

if __name__ == "__main__":
    success = run_pension_coefficient_migration()
    sys.exit(0 if success else 1)
