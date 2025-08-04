"""Add scenario model

Revision ID: 4fc6dac22d14
Revises: f748bf9b733f
Create Date: 2025-08-04 01:00:49.172364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fc6dac22d14'
down_revision: Union[str, Sequence[str], None] = 'f748bf9b733f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('scenario',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('scenario_name', sa.String(length=255), nullable=False),
        sa.Column('parameters', sa.Text(), nullable=False),
        sa.Column('summary_results', sa.Text(), nullable=False),
        sa.Column('cashflow_projection', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scenario')
