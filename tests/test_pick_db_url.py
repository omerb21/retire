"""
Unit tests for app.core.db_url.pick_db_url().

Covers:
- Poisoned DATABASE_URL falls back to a valid alternative key.
- Individual PG* variables are assembled into a URL when no single-URL key works.
- RuntimeError with clear message when nothing is valid.
- Valid DATABASE_URL is picked first.
"""

import os
import pytest
from unittest.mock import patch

from app.core.db_url import pick_db_url, _is_valid_pg_url

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(**kv):
    """Return a dict suitable for monkeypatching os.environ."""
    return kv


# ---------------------------------------------------------------------------
# _is_valid_pg_url unit checks
# ---------------------------------------------------------------------------


class TestIsValidPgUrl:
    def test_valid_postgresql(self):
        assert _is_valid_pg_url("postgresql://user:pass@host:5432/db") is True

    def test_valid_postgres(self):
        assert _is_valid_pg_url("postgres://user:pass@host:5432/db") is True

    def test_rejects_sqlite(self):
        assert _is_valid_pg_url("sqlite:///./retire.db") is False

    def test_rejects_none(self):
        assert _is_valid_pg_url(None) is False

    def test_rejects_empty(self):
        assert _is_valid_pg_url("") is False

    def test_rejects_whitespace(self):
        assert _is_valid_pg_url("postgresql://user:pass@host:5432/db extra") is False

    def test_rejects_shell_command(self):
        assert _is_valid_pg_url('sh -c "postgresql://x"') is False

    def test_rejects_uvicorn_leak(self):
        assert _is_valid_pg_url("postgresql://x uvicorn app.main:app") is False

    def test_rejects_double_ampersand(self):
        assert _is_valid_pg_url("postgresql://x && echo hi") is False

    def test_rejects_quotes(self):
        assert _is_valid_pg_url('"postgresql://user:pass@host/db"') is False

    def test_rejects_python_m(self):
        assert _is_valid_pg_url("python -m alembic postgresql://x") is False


# ---------------------------------------------------------------------------
# pick_db_url integration tests (with env patching)
# ---------------------------------------------------------------------------


class TestPickDbUrl:
    def test_poisoned_database_url_falls_back_to_postgres_url(self):
        env = {
            "DATABASE_URL": 'sh -c "uvicorn app.main:app"',
            "POSTGRES_URL": "postgresql://user:pass@host:5432/mydb",
        }
        with patch.dict(os.environ, env, clear=True):
            url, key = pick_db_url()
        assert url == "postgresql://user:pass@host:5432/mydb"
        assert key == "POSTGRES_URL"

    def test_valid_database_url_picked_first(self):
        env = {
            "DATABASE_URL": "postgresql://a:b@host:5432/db1",
            "POSTGRES_URL": "postgresql://c:d@host:5432/db2",
        }
        with patch.dict(os.environ, env, clear=True):
            url, key = pick_db_url()
        assert url == "postgresql://a:b@host:5432/db1"
        assert key == "DATABASE_URL"

    def test_pg_vars_fallback(self):
        env = {
            "PGHOST": "pg-host.example.com",
            "PGPORT": "5433",
            "PGUSER": "admin",
            "PGPASSWORD": "secret",
            "PGDATABASE": "retire_prod",
        }
        with patch.dict(os.environ, env, clear=True):
            url, key = pick_db_url()
        assert url == "postgresql://admin:secret@pg-host.example.com:5433/retire_prod"
        assert key == "PGHOST+PGUSER+PGPASSWORD+PGDATABASE"

    def test_pg_vars_default_port(self):
        env = {
            "PGHOST": "localhost",
            "PGUSER": "u",
            "PGPASSWORD": "p",
            "PGDATABASE": "d",
        }
        with patch.dict(os.environ, env, clear=True):
            url, key = pick_db_url()
        assert ":5432/" in url

    def test_no_valid_url_raises_runtime_error(self):
        env = {
            "DATABASE_URL": "sqlite:///./retire.db",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="No valid PostgreSQL URL found"):
                pick_db_url()

    def test_completely_empty_env_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="No valid PostgreSQL URL found"):
                pick_db_url()

    def test_extra_keys_checked_first(self):
        env = {
            "MY_CUSTOM_DB": "postgresql://custom:x@host/db",
            "DATABASE_URL": "postgresql://default:x@host/db",
        }
        with patch.dict(os.environ, env, clear=True):
            url, key = pick_db_url(extra_keys=["MY_CUSTOM_DB"])
        assert key == "MY_CUSTOM_DB"

    def test_partial_pg_vars_not_enough(self):
        env = {
            "PGHOST": "host",
            "PGUSER": "user",
            # missing PGPASSWORD and PGDATABASE
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError):
                pick_db_url()
