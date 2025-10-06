"""add_tax_credit_fields_to_client

Revision ID: 755fa723f2ad
Revises: add_server_defaults
Create Date: 2025-10-02 12:41:28.553836

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '755fa723f2ad'
down_revision: Union[str, Sequence[str], None] = 'add_server_defaults'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add tax-related fields
    op.add_column('client', sa.Column('num_children', sa.Integer(), default=0))
    op.add_column('client', sa.Column('is_new_immigrant', sa.Boolean(), default=False))
    op.add_column('client', sa.Column('is_veteran', sa.Boolean(), default=False))
    op.add_column('client', sa.Column('is_disabled', sa.Boolean(), default=False))
    op.add_column('client', sa.Column('disability_percentage', sa.Integer()))
    op.add_column('client', sa.Column('is_student', sa.Boolean(), default=False))
    op.add_column('client', sa.Column('reserve_duty_days', sa.Integer(), default=0))
    
    # Add income and deductions fields
    op.add_column('client', sa.Column('annual_salary', sa.Float()))
    op.add_column('client', sa.Column('pension_contributions', sa.Float(), default=0))
    op.add_column('client', sa.Column('study_fund_contributions', sa.Float(), default=0))
    op.add_column('client', sa.Column('insurance_premiums', sa.Float(), default=0))
    op.add_column('client', sa.Column('charitable_donations', sa.Float(), default=0))
    
    # Add tax credit points fields
    op.add_column('client', sa.Column('tax_credit_points', sa.Float(), default=0))
    op.add_column('client', sa.Column('pension_start_date', sa.Date()))
    op.add_column('client', sa.Column('spouse_income', sa.Float()))
    op.add_column('client', sa.Column('immigration_date', sa.Date()))
    op.add_column('client', sa.Column('military_discharge_date', sa.Date()))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove tax credit points fields
    op.drop_column('client', 'military_discharge_date')
    op.drop_column('client', 'immigration_date')
    op.drop_column('client', 'spouse_income')
    op.drop_column('client', 'pension_start_date')
    op.drop_column('client', 'tax_credit_points')
    
    # Remove income and deductions fields
    op.drop_column('client', 'charitable_donations')
    op.drop_column('client', 'insurance_premiums')
    op.drop_column('client', 'study_fund_contributions')
    op.drop_column('client', 'pension_contributions')
    op.drop_column('client', 'annual_salary')
    
    # Remove tax-related fields
    op.drop_column('client', 'reserve_duty_days')
    op.drop_column('client', 'is_student')
    op.drop_column('client', 'disability_percentage')
    op.drop_column('client', 'is_disabled')
    op.drop_column('client', 'is_veteran')
    op.drop_column('client', 'is_new_immigrant')
    op.drop_column('client', 'num_children')
