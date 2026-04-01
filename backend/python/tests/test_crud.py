import pytest

import uuid
from models import domain
from repositories import crud


@pytest.mark.asyncio
async def test_create_and_get_user_base_case(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name)
    user: domain.User = await crud.get_user(user_id)

    assert user.userId == user_id
    assert user.displayName == display_name


@pytest.mark.asyncio
async def test_create_and_get_music_provider(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await crud.create_music_provider(provider_id, name)
    provider: domain.MusicProvider = await crud.get_music_provider(provider_id)

    assert provider.providerId == provider_id
    assert provider.name == name
