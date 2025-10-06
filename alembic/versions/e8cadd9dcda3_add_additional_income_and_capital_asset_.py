"""add_additional_income_and_capital_asset_tables

Revision ID: e8cadd9dcda3
Revises: 9a24aee2552d
Create Date: 2025-08-20 15:06:44.637490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8cadd9dcda3'
down_revision: Union[str, Sequence[str], None] = '9a24aee2552d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
