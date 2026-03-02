"""add record_status to pension_funds

Revision ID: add_pf_record_status
Revises:
Create Date: 2026-02-13 12:30:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "add_pf_record_status"
down_revision = None  # Update this to the latest revision
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pension_funds", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "record_status", sa.String(20), nullable=False, server_default="active"
            )
        )
        batch_op.create_index(
            "ix_pf_client_type_status",
            ["client_id", "fund_type", "record_status"],
        )


def downgrade():
    with op.batch_alter_table("pension_funds", schema=None) as batch_op:
        batch_op.drop_index("ix_pf_client_type_status")
        batch_op.drop_column("record_status")
