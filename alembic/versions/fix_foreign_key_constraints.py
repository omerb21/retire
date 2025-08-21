"""fix_foreign_key_constraints

Revision ID: fix_foreign_key_constraints
Revises: e8cadd9dcda3
Create Date: 2025-08-20 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_foreign_key_constraints'
down_revision: Union[str, Sequence[str], None] = 'e8cadd9dcda3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop existing foreign keys
    with op.batch_alter_table('additional_income') as batch_op:
        batch_op.drop_constraint('additional_income_client_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'additional_income_client_id_fkey',
            'client', ['client_id'], ['id'],
            ondelete='CASCADE'
        )
    
    with op.batch_alter_table('capital_assets') as batch_op:
        batch_op.drop_constraint('capital_assets_client_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'capital_assets_client_id_fkey',
            'client', ['client_id'], ['id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert foreign keys back to original state
    with op.batch_alter_table('additional_income') as batch_op:
        batch_op.drop_constraint('additional_income_client_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'additional_income_client_id_fkey',
            'clients', ['client_id'], ['id']
        )
    
    with op.batch_alter_table('capital_assets') as batch_op:
        batch_op.drop_constraint('capital_assets_client_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'capital_assets_client_id_fkey',
            'clients', ['client_id'], ['id']
        )
