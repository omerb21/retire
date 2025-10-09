"""Merge multiple heads

Revision ID: 09acfa6107f7
Revises: 755fa723f2ad, add_capital_asset_fields
Create Date: 2025-10-09 14:31:02.135335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09acfa6107f7'
down_revision: Union[str, Sequence[str], None] = ('755fa723f2ad', 'add_capital_asset_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
