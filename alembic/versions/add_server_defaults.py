"""add_server_defaults

Revision ID: add_server_defaults
Revises: fix_foreign_key_constraints
Create Date: 2025-08-20 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_server_defaults'
down_revision: Union[str, Sequence[str], None] = 'fix_foreign_key_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add server_default for indexation_method and tax_treatment in additional_income
    with op.batch_alter_table('additional_income') as batch_op:
        batch_op.alter_column('indexation_method',
                              existing_type=sa.String(20),
                              server_default='none',
                              nullable=False)
        batch_op.alter_column('tax_treatment',
                              existing_type=sa.String(20),
                              server_default='taxable',
                              nullable=False)
    
    # Add server_default for indexation_method and tax_treatment in capital_assets
    with op.batch_alter_table('capital_assets') as batch_op:
        batch_op.alter_column('indexation_method',
                              existing_type=sa.String(20),
                              server_default='none',
                              nullable=False)
        batch_op.alter_column('tax_treatment',
                              existing_type=sa.String(20),
                              server_default='taxable',
                              nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove server_default for indexation_method and tax_treatment in additional_income
    with op.batch_alter_table('additional_income') as batch_op:
        batch_op.alter_column('indexation_method',
                              existing_type=sa.String(20),
                              server_default=None,
                              nullable=False)
        batch_op.alter_column('tax_treatment',
                              existing_type=sa.String(20),
                              server_default=None,
                              nullable=False)
    
    # Remove server_default for indexation_method and tax_treatment in capital_assets
    with op.batch_alter_table('capital_assets') as batch_op:
        batch_op.alter_column('indexation_method',
                              existing_type=sa.String(20),
                              server_default=None,
                              nullable=False)
        batch_op.alter_column('tax_treatment',
                              existing_type=sa.String(20),
                              server_default=None,
                              nullable=False)
