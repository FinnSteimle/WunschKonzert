import os
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Create async engine and session factory lazily
# This allows tests to run without DATABASE_URL environment variable
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_database_url() -> str:
    """Get and format the database URL"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Please set it in your .env file or environment."
        )

    if not database_url.startswith("postgresql+asyncpg"):
        if database_url.startswith("postgresql:"):
            database_url = database_url.replace("postgresql:", "postgresql+asyncpg:", 1)
        else:
            database_url = "postgresql+asyncpg:" + database_url

    return database_url


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Initialize and return the session factory"""
    global _engine, _session_factory
    if _session_factory is None:
        database_url = _get_database_url()
        _engine = create_async_engine(database_url)
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory
