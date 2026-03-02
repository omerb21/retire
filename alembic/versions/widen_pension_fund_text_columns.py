"""widen pension_fund fund_name and remarks to TEXT

Revision ID: widen_pf_text_cols
Revises:
Create Date: 2026-02-13 02:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "widen_pf_text_cols"
down_revision = None  # Update this to the latest revision
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pension_funds", schema=None) as batch_op:
        batch_op.alter_column(
            "fund_name",
            existing_type=sa.String(200),
            type_=sa.Text(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "remarks",
            existing_type=sa.String(500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("pension_funds", schema=None) as batch_op:
        batch_op.alter_column(
            "fund_name",
            existing_type=sa.Text(),
            type_=sa.String(200),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "remarks",
            existing_type=sa.Text(),
            type_=sa.String(500),
            existing_nullable=True,
        )
