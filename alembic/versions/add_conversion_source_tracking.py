"""add conversion source tracking

Revision ID: add_conversion_source
Revises: 09acfa6107f7
Create Date: 2025-10-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_conversion_source'
down_revision = '09acfa6107f7'
branch_labels = None
depends_on = None


def upgrade():
    # Add conversion_source column to pension_funds table
    op.add_column('pension_funds', sa.Column('conversion_source', sa.String(length=1000), nullable=True))
    
    # Add conversion_source column to capital_assets table
    op.add_column('capital_assets', sa.Column('conversion_source', sa.String(length=1000), nullable=True))


def downgrade():
    # Remove conversion_source column from capital_assets table
    op.drop_column('capital_assets', 'conversion_source')
    
    # Remove conversion_source column from pension_funds table
    op.drop_column('pension_funds', 'conversion_source')
