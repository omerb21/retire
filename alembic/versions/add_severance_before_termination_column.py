"""add severance_before_termination column to employment

Revision ID: add_severance_before_termination
Revises: 
Create Date: 2025-01-16 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_severance_before_termination'
down_revision = None  # צריך להגדיר את ה-revision הקודם
branch_labels = None
depends_on = None


def upgrade():
    # Add severance_before_termination column to employment table
    op.add_column('employment', 
        sa.Column('severance_before_termination', sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade():
    # Remove severance_before_termination column from employment table
    op.drop_column('employment', 'severance_before_termination')
