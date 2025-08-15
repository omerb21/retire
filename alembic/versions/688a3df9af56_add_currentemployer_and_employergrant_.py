"""Add CurrentEmployer and EmployerGrant models for Sprint 3

Revision ID: 688a3df9af56
Revises: e640d15a519e
Create Date: 2025-08-11 23:29:03.776436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '688a3df9af56'
down_revision: Union[str, Sequence[str], None] = 'e640d15a519e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create current_employer table
    op.create_table('current_employer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('employer_name', sa.String(length=255), nullable=False),
        sa.Column('employer_id_number', sa.String(length=50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('non_continuous_periods', sa.JSON(), nullable=True),
        sa.Column('last_salary', sa.Float(), nullable=True),
        sa.Column('average_salary', sa.Float(), nullable=True),
        sa.Column('severance_accrued', sa.Float(), nullable=True),
        sa.Column('other_grants', sa.JSON(), nullable=True),
        sa.Column('tax_withheld', sa.Float(), nullable=True),
        sa.Column('grant_installments', sa.JSON(), nullable=True),
        sa.Column('active_continuity', sa.Enum('none', 'severance', 'pension', name='activecontinuitytype'), nullable=True),
        sa.Column('pre_retirement_pension', sa.Float(), nullable=True),
        sa.Column('existing_deductions', sa.JSON(), nullable=True),
        sa.Column('last_update', sa.Date(), nullable=False),
        sa.Column('indexed_severance', sa.Float(), nullable=True),
        sa.Column('severance_exemption_cap', sa.Float(), nullable=True),
        sa.Column('severance_exempt', sa.Float(), nullable=True),
        sa.Column('severance_taxable', sa.Float(), nullable=True),
        sa.Column('severance_tax_due', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create employer_grant table
    op.create_table('employer_grant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employer_id', sa.Integer(), nullable=False),
        sa.Column('grant_type', sa.Enum('severance', 'adjustment', 'other', name='granttype'), nullable=False),
        sa.Column('grant_amount', sa.Float(), nullable=False),
        sa.Column('grant_date', sa.Date(), nullable=False),
        sa.Column('tax_withheld', sa.Float(), nullable=True),
        sa.Column('grant_exempt', sa.Float(), nullable=True),
        sa.Column('grant_taxable', sa.Float(), nullable=True),
        sa.Column('tax_due', sa.Float(), nullable=True),
        sa.Column('indexed_amount', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['employer_id'], ['current_employer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('employer_grant')
    op.drop_table('current_employer')
