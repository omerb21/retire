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


def _has_column(insp, table_name: str, col_name: str) -> bool:
    cols = insp.get_columns(table_name)
    return any(c["name"] == col_name for c in cols)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("scenario"):
        return

    if not _has_column(insp, "scenario", "apply_tax_planning"):
        op.add_column('scenario', sa.Column('apply_tax_planning', sa.Boolean(), nullable=False, server_default='false'))
    if not _has_column(insp, "scenario", "apply_capitalization"):
        op.add_column('scenario', sa.Column('apply_capitalization', sa.Boolean(), nullable=False, server_default='false'))
    if not _has_column(insp, "scenario", "apply_exemption_shield"):
        op.add_column('scenario', sa.Column('apply_exemption_shield', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("scenario"):
        return

    if _has_column(insp, "scenario", "apply_exemption_shield"):
        op.drop_column('scenario', 'apply_exemption_shield')
    if _has_column(insp, "scenario", "apply_capitalization"):
        op.drop_column('scenario', 'apply_capitalization')
    if _has_column(insp, "scenario", "apply_tax_planning"):
        op.drop_column('scenario', 'apply_tax_planning')
