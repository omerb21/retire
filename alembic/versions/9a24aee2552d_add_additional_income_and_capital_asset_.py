"""add_additional_income_and_capital_asset_tables

Revision ID: 9a24aee2552d
Revises: c9e9a73c7bdb
Create Date: 2025-08-20 15:06:21.631329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a24aee2552d'
down_revision: Union[str, Sequence[str], None] = 'c9e9a73c7bdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
