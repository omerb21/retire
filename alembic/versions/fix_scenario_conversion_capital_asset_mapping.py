"""Fix scenario_conversion capital asset mapping

Revision ID: fix_scenario_conversion_capital_asset_mapping
Revises: 755fa723f2ad
Create Date: 2026-01-20

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_scenario_conversion_capital_asset_mapping"
down_revision: Union[str, Sequence[str], None] = "755fa723f2ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ca = sa.table(
        "capital_assets",
        sa.column("current_value", sa.Numeric()),
        sa.column("monthly_income", sa.Numeric()),
        sa.column("payment_frequency", sa.String()),
        sa.column("conversion_source", sa.Text()),
    )

    op.execute(
        ca.update()
        .where(
            sa.and_(
                ca.c.current_value == 0,
                ca.c.monthly_income.isnot(None),
                ca.c.monthly_income > 0,
                ca.c.conversion_source.isnot(None),
                ca.c.conversion_source.like('%"source": "scenario_conversion"%'),
            )
        )
        .values(
            current_value=ca.c.monthly_income,
            monthly_income=0,
            payment_frequency="annually",
        )
    )


def downgrade() -> None:
    ca = sa.table(
        "capital_assets",
        sa.column("current_value", sa.Numeric()),
        sa.column("monthly_income", sa.Numeric()),
        sa.column("payment_frequency", sa.String()),
        sa.column("conversion_source", sa.Text()),
    )

    op.execute(
        ca.update()
        .where(
            sa.and_(
                ca.c.current_value.isnot(None),
                ca.c.current_value > 0,
                ca.c.monthly_income.isnot(None),
                ca.c.monthly_income == 0,
                ca.c.payment_frequency == "annually",
                ca.c.conversion_source.isnot(None),
                ca.c.conversion_source.like('%"source": "scenario_conversion"%'),
            )
        )
        .values(
            monthly_income=ca.c.current_value,
            current_value=0,
            payment_frequency="monthly",
        )
    )
