"""scenario flags and results

Revision ID: 2f21a47b14c3
Revises: 4fc6dac22d14
Create Date: 2025-08-05 14:45:10.996600

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f21a47b14c3'
down_revision: Union[str, Sequence[str], None] = '4fc6dac22d14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add planning flags to scenario table
    op.add_column('scenario', sa.Column('apply_tax_planning', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('scenario', sa.Column('apply_capitalization', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('scenario', sa.Column('apply_exemption_shield', sa.Boolean(), nullable=False, server_default='false'))
    
    # Note: SQLite doesn't support ALTER COLUMN, so we'll rely on the model definition
    # for the updated nullable/default behavior on new records


def downgrade() -> None:
    """Downgrade schema."""
    # Remove planning flags
    op.drop_column('scenario', 'apply_exemption_shield')
    op.drop_column('scenario', 'apply_capitalization')
    op.drop_column('scenario', 'apply_tax_planning')
