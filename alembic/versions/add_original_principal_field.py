"""add original_principal field to capital_assets

Revision ID: add_original_principal
Revises: 
Create Date: 2025-01-29 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'add_original_principal'
down_revision = None  # Update this to the latest revision
branch_labels = None
depends_on = None


def upgrade():
    # Add original_principal column to capital_assets table
    with op.batch_alter_table('capital_assets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('original_principal', sa.Numeric(precision=15, scale=2), nullable=True))


def downgrade():
    # Remove original_principal column from capital_assets table
    with op.batch_alter_table('capital_assets', schema=None) as batch_op:
        batch_op.drop_column('original_principal')
