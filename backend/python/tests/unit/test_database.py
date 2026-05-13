import os
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import core.database
from core.database import _get_database_url, get_session_factory

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "input_url, expected",
    [
        (
            "postgres://postgres:test@localhost:5432/wunschkonzert",
            "postgresql+asyncpg://postgres:test@localhost:5432/wunschkonzert",
        ),
        (
            "postgresql://postgres:test@localhost:5432/wunschkonzert",
            "postgresql+asyncpg://postgres:test@localhost:5432/wunschkonzert",
        ),
        (
            "postgresql+asyncpg://postgres:test@localhost:5432/wunschkonzert",
            "postgresql+asyncpg://postgres:test@localhost:5432/wunschkonzert",
        ),
        (
            "localhost/db",
            "postgresql+asyncpg://localhost/db",
        ),
        (
            "weird-scheme://localhost/db",
            "postgresql+asyncpg://localhost/db",
        ),
        (
            "localhost/db",
            "postgresql+asyncpg://localhost/db",
        ),
    ],
)
def test_get_database_url_formats_correctly(input_url, expected):
    with patch.dict(
        os.environ,
        {"DATABASE_URL": input_url},
    ):
        database_url = _get_database_url()

        assert database_url == expected


def test_get_database_url_raises_error_if_no_environment_variable_set():
    # reset every variable in the file to be tested, for a clean test
    core.database._session_factory = None
    core.database._engine = None

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError):
            get_session_factory()


def test_get_session_factory_is_singleton():
    core.database._session_factory = None
    core.database._engine = None

    # Fake an environment variable
    with patch.dict(
        os.environ,
        {"DATABASE_URL": "postgresql://postgres:test@localhost:5432/wunschkonzert"},
    ):
        factory1 = get_session_factory()
        factory2 = get_session_factory()

        assert factory1 is factory2


# also checks if the engine/session stays the same, as they should
def test_get_session_factory_works_with_correct_values():
    # reset every variable in the file to be tested, for a clean test
    core.database._session_factory = None
    core.database._engine = None

    # expected
    with (
        patch("core.database.create_async_engine") as mock_create_engine,
        patch("core.database.async_sessionmaker") as mock_sessionmaker,
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}),
    ):
        get_session_factory()
        get_session_factory()

    # checks that it uses the created engine and creates an AsyncSession (once)
    mock_create_engine.assert_called_once_with(
        "postgresql+asyncpg://test",
        pool_size=50,
        max_overflow=100,
        pool_timeout=60,
    )
    mock_sessionmaker.assert_called_once_with(
        mock_create_engine.return_value,
        class_=AsyncSession,
        # should be set to false because: if we commit something using our session and we reuse it later,
        # we don't want the session to expire our python objects after a commit.
        # if it did, accessing a property like user.name later would trigger a hidden,
        # synchronous database query to re-fetch the data, which crashes in an async environment.
        expire_on_commit=False,
    )
