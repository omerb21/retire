"""Add pension_fund_coefficient table

Revision ID: add_pension_fund_coefficient
Revises: 
Create Date: 2025-11-02 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_pension_fund_coefficient'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create the pension_fund_coefficient table
    op.create_table('pension_fund_coefficient',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sex', sa.String(length=10), nullable=False),
        sa.Column('retirement_age', sa.Integer(), nullable=False),
        sa.Column('survivors_option', sa.String(length=50), nullable=False),
        sa.Column('spouse_age_diff', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('base_coefficient', sa.Float(), nullable=False),
        sa.Column('adjust_percent', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('fund_name', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for better query performance
    op.create_index(op.f('ix_pension_fund_coefficient_sex'), 'pension_fund_coefficient', ['sex'], unique=False)
    op.create_index(op.f('ix_pension_fund_coefficient_retirement_age'), 'pension_fund_coefficient', ['retirement_age'], unique=False)
    op.create_index(op.f('ix_pension_fund_coefficient_survivors_option'), 'pension_fund_coefficient', ['survivors_option'], unique=False)

def downgrade():
    # Drop the table if we need to rollback
    op.drop_index(op.f('ix_pension_fund_coefficient_survivors_option'), table_name='pension_fund_coefficient')
    op.drop_index(op.f('ix_pension_fund_coefficient_retirement_age'), table_name='pension_fund_coefficient')
    op.drop_index(op.f('ix_pension_fund_coefficient_sex'), table_name='pension_fund_coefficient')
    op.drop_table('pension_fund_coefficient')
