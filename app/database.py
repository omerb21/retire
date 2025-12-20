"""
Database configuration module for SQLAlchemy and connection management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Get database URL from dedicated env var or use default SQLite for development
# IMPORTANT: We intentionally ignore generic DATABASE_URL to avoid accidental
# sharing of a database with other systems (e.g. external CRM).
PLANNING_DATABASE_URL = os.getenv("PLANNING_DATABASE_URL")
DATABASE_URL = PLANNING_DATABASE_URL or "sqlite:///./retire.db"

# Create base class for declarative models
Base = declarative_base()

def get_engine(url=None):
    """Get SQLAlchemy engine with proper configuration"""
    url = url or DATABASE_URL
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
            conn.execute(text(f"ALTER TABLE client ADD COLUMN {col_name} {col_type_sql}"))

        def add_column_postgres_like(conn, col_name: str, col_type_sql: str):
            conn.execute(text(f"ALTER TABLE client ADD COLUMN IF NOT EXISTS {col_name} {col_type_sql}"))

        with engine.begin() as conn:
            add_column = add_column_sqlite if dialect == "sqlite" else add_column_postgres_like

            if "public_chat_token_balance" not in columns:
                add_column(conn, "public_chat_token_balance", "INTEGER")
                conn.execute(text("UPDATE client SET public_chat_token_balance = 0 WHERE public_chat_token_balance IS NULL"))

            if "public_chat_tokens_spent" not in columns:
                add_column(conn, "public_chat_tokens_spent", "INTEGER")
                conn.execute(text("UPDATE client SET public_chat_tokens_spent = 0 WHERE public_chat_tokens_spent IS NULL"))

            if "public_chat_credit_initialized" not in columns:
                add_column(conn, "public_chat_credit_initialized", "BOOLEAN" if dialect != "sqlite" else "INTEGER")
                conn.execute(text("UPDATE client SET public_chat_credit_initialized = 0 WHERE public_chat_credit_initialized IS NULL"))
    except Exception:
        # best-effort only; avoid breaking app startup
        return

# Create SQLAlchemy engine
engine = get_engine()

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


