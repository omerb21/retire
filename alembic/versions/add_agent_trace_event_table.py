"""add agent_trace_event table

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_trace_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False, index=True),
        sa.Column("session_id", sa.String(128), nullable=True, index=True),
        sa.Column("client_id", sa.Integer(), nullable=True, index=True),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("payload_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )
    op.create_index(
        "ix_agent_trace_event_trace_created",
        "agent_trace_event",
        ["trace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_trace_event_trace_created", table_name="agent_trace_event")
    op.drop_table("agent_trace_event")
