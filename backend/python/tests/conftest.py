import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from testcontainers.postgres import PostgresContainer
from models.domain import Base
import core.database

"""
This file makes sure we dont use the acutal database for our unit tests.
It creates a brand new psql-container, creates an engine and session to use for our tests.
"""

@pytest.fixture(scope="session")
def postgres_container():
    """Spin up a Postgres container for the whole test session."""
    with PostgresContainer("postgres:17-alpine") as postgres:
        yield postgres


@pytest.fixture(scope="session")
async def db_engine(postgres_container):
    """Create a database engine for the test container."""
    # Get the base URL from testcontainers
    url = postgres_container.get_connection_url()

    # Force the use of asyncpg driver
    # We replace any postgres(ql):// prefix with postgresql+asyncpg://
    if "://" in url:
        _, address = url.split("://", 1)
        url = f"postgresql+asyncpg://{address}"

    # Overwrite the environment variable so core.database uses it
    os.environ["DATABASE_URL"] = url

    engine = create_async_engine(url)

    # Create tables
    async with engine.begin() as conn:
        # We need to make sure enums are created correctly for Postgres
        # Base.metadata.create_all handles this if configured correctly
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Get a fresh database session for each test."""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Mock core.database.get_session_factory to return this session factory
    # This allows crud.py functions to use our test database
    original_get_session_factory = core.database.get_session_factory
    core.database.get_session_factory = lambda: session_factory

    async with session_factory() as session:
        yield session
        # Rollback any changes after each test to keep tests isolated
        await session.rollback()

    # Restore original function
    core.database.get_session_factory = original_get_session_factory
