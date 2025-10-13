"""Add conversion_source columns to pension_funds and capital_assets tables"""
from sqlalchemy import create_engine, text

# Create engine
engine = create_engine('sqlite:///./retire.db')

with engine.connect() as conn:
    try:
        # Add column to pension_funds
        conn.execute(text('ALTER TABLE pension_funds ADD COLUMN conversion_source VARCHAR(1000)'))
        print('✓ Added conversion_source to pension_funds')
    except Exception as e:
        print(f'pension_funds: {e}')
    
    try:
        # Add column to capital_assets
        conn.execute(text('ALTER TABLE capital_assets ADD COLUMN conversion_source VARCHAR(1000)'))
        print('✓ Added conversion_source to capital_assets')
    except Exception as e:
        print(f'capital_assets: {e}')
    
    conn.commit()
    print('\n✓ Migration completed successfully!')
