"""update tax_rate field to support 0-99 percentage

Revision ID: update_tax_rate_001
Revises: 
Create Date: 2025-10-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'update_tax_rate_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Drop the old constraint
    op.drop_constraint('check_valid_tax_rate', 'additional_income', type_='check')
    
    # Alter the column type from Numeric(5,4) to Numeric(5,2)
    op.alter_column('additional_income', 'tax_rate',
                    type_=sa.Numeric(5, 2),
                    existing_type=sa.Numeric(5, 4),
                    existing_nullable=True)
    
    # Add the new constraint (0-99)
    op.create_check_constraint(
        'check_valid_tax_rate',
        'additional_income',
        'tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 99)'
    )


def downgrade():
    # Drop the new constraint
    op.drop_constraint('check_valid_tax_rate', 'additional_income', type_='check')
    
    # Revert the column type
    op.alter_column('additional_income', 'tax_rate',
                    type_=sa.Numeric(5, 4),
                    existing_type=sa.Numeric(5, 2),
                    existing_nullable=True)
    
    # Add back the old constraint (0-1)
    op.create_check_constraint(
        'check_valid_tax_rate',
        'additional_income',
        'tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)'
    )
