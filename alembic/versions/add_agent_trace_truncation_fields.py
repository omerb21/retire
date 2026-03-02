"""add is_truncated and payload_size to agent_trace_event

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-10
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_trace_event") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_truncated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        batch_op.add_column(
            sa.Column("payload_size", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_trace_event") as batch_op:
        batch_op.drop_column("payload_size")
        batch_op.drop_column("is_truncated")
