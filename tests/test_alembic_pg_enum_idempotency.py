import os

import pytest


def test_alembic_upgrade_head_enum_idempotent() -> None:
    db_url = os.getenv("TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("TEST_DATABASE_URL not set; skipping Postgres alembic enum idempotency test")

    from scripts.test_alembic_pg_enum_idempotency import run

    run(db_url)
