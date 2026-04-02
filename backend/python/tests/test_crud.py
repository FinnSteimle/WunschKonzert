import pytest

import uuid
from models import domain
from repositories import crud

from core.exceptions import (
    ResourceExistsError,
)


@pytest.mark.asyncio
async def test_create_and_get_user_base_case(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name, db_session)
    user: domain.User = await crud.get_user(user_id, db_session)

    assert user.userId == user_id
    assert user.displayName == display_name


@pytest.mark.asyncio
async def test_create_user_that_exists_throws_error(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name, db_session)

    with pytest.raises(ResourceExistsError):
        await crud.create_user(user_id, display_name, db_session)


@pytest.mark.asyncio
async def test_create_and_get_music_provider(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await crud.create_music_provider(provider_id, name, db_session)
    provider: domain.MusicProvider = await crud.get_music_provider(
        provider_id, db_session
    )

    assert provider.providerId == provider_id
    assert provider.name == name


@pytest.mark.asyncio
async def test_create_provider_that_exists_throws_error(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await crud.create_music_provider(provider_id, name, db_session)

    with pytest.raises(ResourceExistsError):
        await crud.create_music_provider(provider_id, name, db_session)
