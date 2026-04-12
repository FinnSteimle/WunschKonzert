import os
import uuid
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

import core.database
from models.domain import Base
from repositories import crud
from services import room_service

"""
This file contains helper fuctions and makes sure we dont use the acutal database for our unit tests.
It creates a brand new psql-container, creates an engine and session to use for our tests.
"""


@pytest.fixture(scope="session")
def postgres_container():
    """Spin up a Postgres container for the whole test session."""
    postgres_image = os.getenv("POSTGRES_TEST_IMAGE", "postgres:17-alpine")
    with PostgresContainer(postgres_image) as postgres:
        yield postgres


@pytest.fixture(scope="session")
async def db_engine(postgres_container):
    """Create a database engine for the test container."""
    url = postgres_container.get_connection_url()

    # Force the use of asyncpg driver
    if "://" in url:
        _, address = url.split("://", 1)
        url = f"postgresql+asyncpg://{address}"

    os.environ["DATABASE_URL"] = url

    # NullPool: no connection pooling — prevents deadlocks when db_session
    # holds a connection while CRUD functions check out additional ones.
    engine = create_async_engine(url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine):
    """Single shared session factory for the whole test session."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    """Get a fresh database session for each test."""
    original_get_session_factory = core.database.get_session_factory
    original_crud_get_session_factory = crud.get_session_factory
    original_session_factory_singleton = core.database._session_factory
    original_engine_singleton = core.database._engine

    # Keep all DB access on the real test factory for this test case.
    core.database._session_factory = session_factory
    core.database.get_session_factory = lambda: session_factory
    crud.get_session_factory = lambda: session_factory

    async with session_factory() as session:
        yield session
        # Truncate all tables after each test — rollback alone cannot undo
        # commits made by CRUD functions that open their own sessions
        await session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()

    # Clear the room state cache to prevent memory accumulation across tests
    room_service.room_state_cache.clear()

    core.database._engine = original_engine_singleton
    core.database._session_factory = original_session_factory_singleton
    crud.get_session_factory = original_crud_get_session_factory
    core.database.get_session_factory = original_get_session_factory


@pytest.fixture
def init_room(db_session):
    async def _factory(
        provider_id=None,
        provider_name=None,
        room_name="test_room",
        user_id=None,
    ):

        provider_id = provider_id or str(uuid.uuid4())
        provider_name = provider_name or f"provider_{str(uuid.uuid4())[:8]}"
        user_id = user_id or str(uuid.uuid4())

        await crud.create_user(user_id, "test_host", db_session)
        await crud.create_music_provider(provider_id, provider_name, db_session)
        await db_session.commit()

        provider = await crud.get_music_provider(provider_id, db_session)

        room = await crud.create_room(room_name, user_id, provider.providerId)
        await crud.create_room_membership(user_id, room.roomId)
        return room

    return _factory


@pytest.fixture
async def client(db_session):
    """
    Get a fresh FastAPI test client for each test.
    We mock lifespan activities like migrations and seeding to avoid side effects.
    """
    from main import app

    with patch("main.run_migrations"), patch("main.initialize_music_providers"):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            yield ac


@pytest.fixture
def websocket_client(db_session):
    """
    Get a fresh FastAPI TestClient for websocket testing.
    We mock lifespan activities like migrations and seeding to avoid side effects.
    """
    from fastapi.testclient import TestClient

    from main import app

    with patch("main.run_migrations"), patch("main.initialize_music_providers"):
        return TestClient(app)
