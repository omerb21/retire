"""merge all heads

Revision ID: d2e48a6d7377
Revises: b2c3d4e5f6a7, add_original_principal, add_pf_record_status, add_severance_before_termination, fix_scenario_conversion_capital_asset_mapping, update_tax_rate_001, widen_pf_text_cols
Create Date: 2026-02-13 14:11:44.993092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e48a6d7377'
down_revision: Union[str, Sequence[str], None] = ('b2c3d4e5f6a7', 'add_original_principal', 'add_pf_record_status', 'add_severance_before_termination', 'fix_scenario_conversion_capital_asset_mapping', 'update_tax_rate_001', 'widen_pf_text_cols')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
