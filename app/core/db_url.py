"""
Resilient database URL picker for production environments (Railway, Render, etc.).

Scans multiple well-known environment variables, validates each candidate,
and returns the first valid PostgreSQL URL.  Falls back to constructing a URL
from individual PG* variables when no single-URL variable is usable.

Usage:
    from app.core.db_url import pick_db_url
    db_url, picked_from = pick_db_url()
"""

import logging
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger("app.core.db_url")

# Ordered list of env-var names to probe (most specific first).
_CANDIDATE_KEYS: list[str] = [
    "DATABASE_URL",
    "DB_URL",
    "DATABASE_PRIVATE_URL",
    "DATABASE_PUBLIC_URL",
    "POSTGRES_URL",
    "POSTGRESQL_URL",
    "PGDATABASE_URL",
    "DATABASE_URL_RAILWAY",
    "RAILWAY_DATABASE_URL",
]

# Patterns that indicate the value was poisoned by a shell wrapper / start cmd.
_POISON_PATTERNS: list[re.Pattern] = [
    re.compile(r"\s"),  # whitespace anywhere
    re.compile(r'["\']'),  # quotes
    re.compile(r"sh\s+-c"),  # shell invocation
    re.compile(r"&&"),  # chained commands
    re.compile(r"uvicorn"),  # start command leaked
    re.compile(r"python\s+-m"),  # start command leaked
]


def _is_valid_pg_url(value: Optional[str]) -> bool:
    """Return True if *value* looks like a usable PostgreSQL connection URL."""
    if not value:
        return False
    if not (value.startswith("postgresql://") or value.startswith("postgres://")):
        return False
    for pat in _POISON_PATTERNS:
        if pat.search(value):
            return False
    return True


def _build_url_from_pg_vars() -> Optional[str]:
    """Attempt to build a PostgreSQL URL from individual PG* env vars."""
    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    database = os.getenv("PGDATABASE")

    if not all([host, user, password, database]):
        return None

    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def pick_db_url(
    extra_keys: Optional[list[str]] = None,
) -> Tuple[str, str]:
    """Return ``(db_url, picked_from_key)`` or raise ``RuntimeError``.

    Parameters
    ----------
    extra_keys:
        Additional env-var names to probe *before* the built-in list.
    """
    keys_to_try = list(extra_keys or []) + _CANDIDATE_KEYS
    checked: list[str] = []

    for key in keys_to_try:
        raw = os.getenv(key)
        if raw is None:
            continue
        checked.append(key)
        if _is_valid_pg_url(raw):
            return raw, key
        else:
            logger.warning("DB URL candidate %s rejected (invalid or poisoned)", key)

    # Fallback: build from individual PG* variables
    built = _build_url_from_pg_vars()
    if built and _is_valid_pg_url(built):
        return built, "PGHOST+PGUSER+PGPASSWORD+PGDATABASE"

    raise RuntimeError(
        "No valid PostgreSQL URL found. "
        f"Checked env keys: {checked or keys_to_try}. "
        "Set DATABASE_URL or individual PG* variables to a valid postgresql:// URL."
    )
