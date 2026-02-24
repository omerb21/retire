import os
import subprocess
import sys
from contextlib import contextmanager
from urllib.parse import urlparse

from sqlalchemy import create_engine, text


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required env var: {key}")
    return value.strip()


def _validate_pg_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError(
            f"TEST_DATABASE_URL must be a PostgreSQL URL (postgresql://...). Got scheme={parsed.scheme!r}"
        )


@contextmanager
def _engine(url: str):
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        yield engine
    finally:
        engine.dispose()


def _recreate_schema(engine, schema: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))


def _drop_schema(engine, schema: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def _ensure_activecontinuitytype_in_schema(engine, schema: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typname = 'activecontinuitytype'
                          AND n.nspname = :schema
                    ) THEN
                        EXECUTE 'CREATE TYPE ' || quote_ident(:schema) || '.activecontinuitytype AS ENUM (''none'', ''severance'', ''pension'')';
                    END IF;
                END $$;
                """),
            {"schema": schema},
        )


def _run_alembic_upgrade(schema: str, db_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["PGOPTIONS"] = f"-c search_path={schema},public"

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=env,
    )


def _assert_table_exists(engine, schema: str, table: str) -> None:
    with engine.connect() as conn:
        full = f"{schema}.{table}"
        res = conn.execute(text("SELECT to_regclass(:full)"), {"full": full}).scalar()
        if res is None:
            raise AssertionError(f"Expected table to exist: {full}")


def run(db_url: str) -> None:
    _validate_pg_url(db_url)

    schema_clean = "alembic_clean"
    schema_enum_exists = "alembic_enum_exists"

    with _engine(db_url) as engine:
        try:
            # Test 1: clean schema, no pre-created enum
            _recreate_schema(engine, schema_clean)
            _run_alembic_upgrade(schema_clean, db_url)
            _assert_table_exists(engine, schema_clean, "current_employer")
            _assert_table_exists(engine, schema_clean, "employer_grant")

            # Test 2: schema where enum already exists before alembic
            _recreate_schema(engine, schema_enum_exists)
            _ensure_activecontinuitytype_in_schema(engine, schema_enum_exists)
            _run_alembic_upgrade(schema_enum_exists, db_url)
            _assert_table_exists(engine, schema_enum_exists, "current_employer")
            _assert_table_exists(engine, schema_enum_exists, "employer_grant")
        finally:
            _drop_schema(engine, schema_clean)
            _drop_schema(engine, schema_enum_exists)


def main() -> int:
    try:
        db_url = os.getenv("TEST_DATABASE_URL") or _require_env("DATABASE_URL")
        run(db_url)
        print("OK: alembic schema migrations passed (clean + enum exists)")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
