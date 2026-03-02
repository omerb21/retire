"""scenario flags and results

Revision ID: 2f21a47b14c3
Revises: 4fc6dac22d14
Create Date: 2025-08-05 14:45:10.996600

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f21a47b14c3"
down_revision: Union[str, Sequence[str], None] = "4fc6dac22d14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("scenario"):
        return

    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS apply_tax_planning BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS apply_capitalization BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE scenario ADD COLUMN IF NOT EXISTS apply_exemption_shield BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("scenario"):
        return

    op.execute("ALTER TABLE scenario DROP COLUMN IF EXISTS apply_exemption_shield")
    op.execute("ALTER TABLE scenario DROP COLUMN IF EXISTS apply_capitalization")
    op.execute("ALTER TABLE scenario DROP COLUMN IF EXISTS apply_tax_planning")
