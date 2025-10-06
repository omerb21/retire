"""reconcile scenario columns

Revision ID: dc8c7ed566bc
Revises: 2f21a47b14c3
Create Date: 2025-08-05 18:32:20.874970

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc8c7ed566bc'
down_revision: Union[str, Sequence[str], None] = '2f21a47b14c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - reconcile scenario columns."""
    # This migration reconciles the state where columns already exist
    # No actual changes needed - just marking as applied
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns if they exist
    with op.batch_alter_table('scenario', schema=None) as batch_op:
        columns_to_remove = ['apply_tax_planning', 'apply_capitalization', 'apply_exemption_shield', 'cashflow_projection', 'summary_results']
        for col_name in columns_to_remove:
            try:
                batch_op.drop_column(col_name)
            except:
                pass  # Column might not exist
