"""
Database configuration module for SQLAlchemy and connection management
"""

import logging
import os
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker


# ---------------------------------------------------------------------------
# Resolve the database URL.  In production we MUST connect to Postgres.
# In local dev (no PG env vars at all) we fall back to SQLite.
# ---------------------------------------------------------------------------
def _resolve_database_url() -> tuple[str, str]:
    """Return (url, source_label).  Tries pick_db_url first, falls back to SQLite for dev."""
    # PLANNING_DATABASE_URL takes absolute priority if set
    planning_url = os.getenv("PLANNING_DATABASE_URL")
    if planning_url and (
        planning_url.startswith("postgresql://")
        or planning_url.startswith("postgres://")
    ):
        return planning_url, "PLANNING_DATABASE_URL"

    # In local dev we may explicitly set DATABASE_URL to sqlite.
    env_db_url = os.getenv("DATABASE_URL")
    if env_db_url and env_db_url.startswith("sqlite"):
        return env_db_url, "DATABASE_URL"

    try:
        from app.core.db_url import pick_db_url

        url, key = pick_db_url()
        return url, key
    except RuntimeError:
        # No valid Postgres URL anywhere → local dev fallback
        return "sqlite:///./retire.db", "sqlite_fallback"


_db_url, _db_url_source = _resolve_database_url()
DATABASE_URL = _db_url

_startup_logger = logging.getLogger("app.database")
_startup_logger.info(
    "DB selected from=%s scheme=%s", _db_url_source, DATABASE_URL.split(":", 1)[0]
)

# Create base class for declarative models
Base = declarative_base()


def get_engine(url=None):
    """Get SQLAlchemy engine with proper configuration"""
    url = url or DATABASE_URL
    try:
        parsed_url = make_url(url)
        if (
            (parsed_url.drivername or "").startswith("sqlite")
            and parsed_url.database
            and parsed_url.database != ":memory:"
        ):
            db_path = parsed_url.database
            if not os.path.isabs(db_path):
                parsed_url = parsed_url.set(database=os.path.abspath(db_path))
                url = str(parsed_url)
                db_path = parsed_url.database

            try:
                parent = os.path.dirname(db_path)
                if parent and (not os.path.exists(parent)):
                    os.makedirs(parent, exist_ok=True)
            except Exception:
                pass
    except Exception:
        pass
    is_sqlite = url.startswith("sqlite")

    # SQLite needs special connect args, but we don't use pooling settings there
    connect_args = {"check_same_thread": False} if is_sqlite else {}

    engine_kwargs = {}
    if not is_sqlite:
        # On managed Postgres (Render) connections can be killed after idle time.
        # pool_pre_ping verifies connections before use, and pool_recycle forces
        # periodic reconnection to avoid using dead connections.
        engine_kwargs.update(
            pool_pre_ping=True,
            pool_recycle=600,  # recycle connections every 10 minutes
            pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        )

    return create_engine(url, connect_args=connect_args, **engine_kwargs)


def setup_database(engine):
    """Setup database with proper mapper clearing"""
    from sqlalchemy.orm import clear_mappers

    clear_mappers()
    Base.metadata.create_all(bind=engine)


def ensure_client_public_chat_credit_schema(engine) -> None:
    """Ensure client table contains columns required for per-client public chat credit.

    This is a non-destructive best-effort schema fix for environments without Alembic.
    """

    try:
        inspector = inspect(engine)
        if "client" not in set(inspector.get_table_names() or []):
            return

        columns = {c.get("name") for c in (inspector.get_columns("client") or [])}
        dialect = (engine.dialect.name or "").lower()

        def add_column_sqlite(conn, col_name: str, col_type_sql: str):
            conn.execute(
                text(f"ALTER TABLE client ADD COLUMN {col_name} {col_type_sql}")
            )

        def add_column_postgres_like(conn, col_name: str, col_type_sql: str):
            conn.execute(
                text(
                    f"ALTER TABLE client ADD COLUMN IF NOT EXISTS {col_name} {col_type_sql}"
                )
            )

        with engine.begin() as conn:
            add_column = (
                add_column_sqlite if dialect == "sqlite" else add_column_postgres_like
            )

            if "public_chat_token_balance" not in columns:
                add_column(conn, "public_chat_token_balance", "INTEGER")
                conn.execute(
                    text(
                        "UPDATE client SET public_chat_token_balance = 0 WHERE public_chat_token_balance IS NULL"
                    )
                )

            if "public_chat_tokens_spent" not in columns:
                add_column(conn, "public_chat_tokens_spent", "INTEGER")
                conn.execute(
                    text(
                        "UPDATE client SET public_chat_tokens_spent = 0 WHERE public_chat_tokens_spent IS NULL"
                    )
                )

            if "public_chat_credit_initialized" not in columns:
                add_column(
                    conn,
                    "public_chat_credit_initialized",
                    "BOOLEAN" if dialect != "sqlite" else "INTEGER",
                )
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "UPDATE client SET public_chat_credit_initialized = 0 WHERE public_chat_credit_initialized IS NULL"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "UPDATE client SET public_chat_credit_initialized = FALSE WHERE public_chat_credit_initialized IS NULL"
                        )
                    )
    except Exception:
        # best-effort only; avoid breaking app startup
        return


def ensure_agent_trace_event_schema(engine) -> None:
    """Best-effort migration: add is_truncated / payload_size to agent_trace_event."""
    try:
        inspector = inspect(engine)
        if "agent_trace_event" not in set(inspector.get_table_names() or []):
            return
        columns = {
            c.get("name") for c in (inspector.get_columns("agent_trace_event") or [])
        }
        dialect = (engine.dialect.name or "").lower()

        with engine.begin() as conn:
            if "is_truncated" not in columns:
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "ALTER TABLE agent_trace_event ADD COLUMN is_truncated INTEGER NOT NULL DEFAULT 0"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE agent_trace_event ADD COLUMN IF NOT EXISTS is_truncated BOOLEAN NOT NULL DEFAULT FALSE"
                        )
                    )
            if "payload_size" not in columns:
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "ALTER TABLE agent_trace_event ADD COLUMN payload_size INTEGER"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE agent_trace_event ADD COLUMN IF NOT EXISTS payload_size INTEGER"
                        )
                    )
    except Exception:
        return


def ensure_pension_funds_record_status_schema(engine) -> None:
    """Best-effort migration for environments without Alembic.

    Ensures pension_funds.record_status exists (and a supporting index), which is
    required by the ORM model.
    """
    try:
        inspector = inspect(engine)
        if "pension_funds" not in set(inspector.get_table_names() or []):
            return

        columns = {
            c.get("name") for c in (inspector.get_columns("pension_funds") or [])
        }
        dialect = (engine.dialect.name or "").lower()

        with engine.begin() as conn:
            if "record_status" not in columns:
                if dialect == "sqlite":
                    conn.execute(
                        text(
                            "ALTER TABLE pension_funds "
                            "ADD COLUMN record_status VARCHAR(20) NOT NULL DEFAULT 'active'"
                        )
                    )
                else:
                    conn.execute(
                        text(
                            "ALTER TABLE pension_funds "
                            "ADD COLUMN IF NOT EXISTS record_status VARCHAR(20) NOT NULL DEFAULT 'active'"
                        )
                    )

            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_pf_client_type_status "
                        "ON pension_funds (client_id, fund_type, record_status)"
                    )
                )
            else:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_pf_client_type_status "
                        "ON pension_funds (client_id, fund_type, record_status)"
                    )
                )
    except Exception:
        return


# Create SQLAlchemy engine
engine = get_engine()

_logger = logging.getLogger("app.database")
try:
    _engine_url = make_url(str(engine.url))
    if _engine_url.password is not None:
        _safe_url = str(_engine_url.set(password="***"))
    else:
        _safe_url = str(_engine_url)
    _logger.info("DB_URL=%s", _safe_url)
    if (
        (_engine_url.drivername or "").startswith("sqlite")
        and _engine_url.database
        and _engine_url.database != ":memory:"
    ):
        _logger.info("SQLITE_PATH=%s", _engine_url.database)
except Exception:
    pass

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency for FastAPI to get database session

    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
