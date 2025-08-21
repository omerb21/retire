"""add_additional_income_and_capital_asset_tables

Revision ID: c9e9a73c7bdb
Revises: 688a3df9af56
Create Date: 2025-08-20 13:38:28.578301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e9a73c7bdb'
down_revision: Union[str, Sequence[str], None] = '688a3df9af56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create additional_income table
    op.create_table('additional_income',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('frequency', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('indexation_method', sa.String(length=20), nullable=False),
        sa.Column('fixed_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('tax_treatment', sa.String(length=20), nullable=False),
        sa.Column('tax_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('remarks', sa.String(length=500), nullable=True),
        sa.CheckConstraint('amount > 0', name='check_positive_amount'),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='check_valid_date_range'),
        sa.CheckConstraint("indexation_method != 'fixed' OR fixed_rate IS NOT NULL", name='check_fixed_rate_when_fixed_indexation'),
        sa.CheckConstraint("tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL", name='check_tax_rate_when_fixed_tax'),
        sa.CheckConstraint('fixed_rate IS NULL OR fixed_rate >= 0', name='check_non_negative_fixed_rate'),
        sa.CheckConstraint('tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)', name='check_valid_tax_rate'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_additional_income_id'), 'additional_income', ['id'], unique=False)
    op.create_index(op.f('ix_additional_income_client_id'), 'additional_income', ['client_id'], unique=False)

    # Create capital_assets table
    op.create_table('capital_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('asset_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('current_value', sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column('annual_return_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('payment_frequency', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('indexation_method', sa.String(length=20), nullable=False),
        sa.Column('fixed_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('tax_treatment', sa.String(length=20), nullable=False),
        sa.Column('tax_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('remarks', sa.String(length=500), nullable=True),
        sa.CheckConstraint('current_value > 0', name='check_positive_value'),
        sa.CheckConstraint('annual_return_rate >= 0', name='check_non_negative_return'),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='check_valid_date_range'),
        sa.CheckConstraint("indexation_method != 'fixed' OR fixed_rate IS NOT NULL", name='check_fixed_rate_when_fixed_indexation'),
        sa.CheckConstraint("tax_treatment != 'fixed_rate' OR tax_rate IS NOT NULL", name='check_tax_rate_when_fixed_tax'),
        sa.CheckConstraint('fixed_rate IS NULL OR fixed_rate >= 0', name='check_non_negative_fixed_rate'),
        sa.CheckConstraint('tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)', name='check_valid_tax_rate'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_capital_assets_id'), 'capital_assets', ['id'], unique=False)
    op.create_index(op.f('ix_capital_assets_client_id'), 'capital_assets', ['client_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop capital_assets table
    op.drop_index(op.f('ix_capital_assets_client_id'), table_name='capital_assets')
    op.drop_index(op.f('ix_capital_assets_id'), table_name='capital_assets')
    op.drop_table('capital_assets')
    
    # Drop additional_income table
    op.drop_index(op.f('ix_additional_income_client_id'), table_name='additional_income')
    op.drop_index(op.f('ix_additional_income_id'), table_name='additional_income')
    op.drop_table('additional_income')
