import uuid

import pytest

from core.exceptions import ResourceExistsError
from models import domain
from repositories import music_provider_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_and_get_music_provider(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await music_provider_repo.create_music_provider(provider_id, name, db_session)
    provider: domain.MusicProvider = await music_provider_repo.get_music_provider(
        provider_id, db_session
    )

    assert provider.providerId == provider_id
    assert provider.name == name


@pytest.mark.asyncio
async def test_create_provider_that_exists_throws_error(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await music_provider_repo.create_music_provider(provider_id, name, db_session)

    with pytest.raises(ResourceExistsError):
        await music_provider_repo.create_music_provider(provider_id, name, db_session)
