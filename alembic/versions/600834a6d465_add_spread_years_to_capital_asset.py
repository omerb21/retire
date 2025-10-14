"""add spread_years to capital_asset

Revision ID: 600834a6d465
Revises: add_conversion_source
Create Date: 2025-10-14 17:46:28.066330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '600834a6d465'
down_revision: Union[str, Sequence[str], None] = 'add_conversion_source'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add spread_years column to capital_assets table
    op.add_column('capital_assets', sa.Column('spread_years', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove spread_years column
    op.drop_column('capital_assets', 'spread_years')
