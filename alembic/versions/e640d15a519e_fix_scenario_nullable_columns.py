"""fix scenario nullable columns

Revision ID: e640d15a519e
Revises: dc8c7ed566bc
Create Date: 2025-08-06 21:17:55.984118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e640d15a519e'
down_revision: Union[str, Sequence[str], None] = 'dc8c7ed566bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - make summary_results and cashflow_projection nullable."""
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # First, create a new table with the correct schema
    op.create_table('scenario_new',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('scenario_name', sa.String(length=255), nullable=False),
        sa.Column('apply_tax_planning', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('apply_capitalization', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('apply_exemption_shield', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('parameters', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('summary_results', sa.Text(), nullable=True),  # Now nullable
        sa.Column('cashflow_projection', sa.Text(), nullable=True),  # Now nullable
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table to new table
    op.execute("""
        INSERT INTO scenario_new (id, client_id, scenario_name, apply_tax_planning, 
                                 apply_capitalization, apply_exemption_shield, parameters, 
                                 summary_results, cashflow_projection, created_at)
        SELECT id, client_id, scenario_name, 
               COALESCE(apply_tax_planning, 0),
               COALESCE(apply_capitalization, 0), 
               COALESCE(apply_exemption_shield, 0),
               COALESCE(parameters, '{}'),
               summary_results, cashflow_projection, created_at
        FROM scenario
    """)
    
    # Drop old table and rename new table
    op.drop_table('scenario')
    op.rename_table('scenario_new', 'scenario')


def downgrade() -> None:
    """Downgrade schema - make summary_results and cashflow_projection NOT NULL again."""
    # Recreate table with NOT NULL constraints
    op.create_table('scenario_old',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('scenario_name', sa.String(length=255), nullable=False),
        sa.Column('apply_tax_planning', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('apply_capitalization', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('apply_exemption_shield', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('parameters', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('summary_results', sa.Text(), nullable=False),  # Back to NOT NULL
        sa.Column('cashflow_projection', sa.Text(), nullable=False),  # Back to NOT NULL
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data back (only records with non-null values)
    op.execute("""
        INSERT INTO scenario_old (id, client_id, scenario_name, apply_tax_planning,
                                 apply_capitalization, apply_exemption_shield, parameters,
                                 summary_results, cashflow_projection, created_at)
        SELECT id, client_id, scenario_name, apply_tax_planning,
               apply_capitalization, apply_exemption_shield, parameters,
               summary_results, cashflow_projection, created_at
        FROM scenario
        WHERE summary_results IS NOT NULL AND cashflow_projection IS NOT NULL
    """)
    
    # Drop new table and rename old table back
    op.drop_table('scenario')
    op.rename_table('scenario_old', 'scenario')
