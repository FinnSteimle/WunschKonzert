import uuid

import pytest

from core.exceptions import ResourceNotFoundError
from repositories import music_provider_repo, room_repo, user_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_room(db_session):
    user_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "host", db_session)
    await music_provider_repo.create_music_provider(provider_id, "Spotify", db_session)
    await db_session.flush()

    room = await room_repo.create_room(
        user_id, provider_id, "My Custom Room", db_session
    )

    assert room.name == "My Custom Room"
    assert room.hostedBy == user_id
    assert room.supportedProviderId == provider_id
    assert room.joinCode is not None


@pytest.mark.asyncio
async def test_create_room_with_default_name(db_session):
    user_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "host", db_session)
    await music_provider_repo.create_music_provider(provider_id, "Spotify", db_session)
    await db_session.flush()

    room = await room_repo.create_room(user_id, provider_id, session=db_session)

    assert room.name == f"Room_{room.joinCode}"
    assert room.hostedBy == user_id


@pytest.mark.asyncio
async def test_get_room_by_join_code(db_session, init_room):
    room = await init_room()

    room_by_code = await room_repo.get_room_by_join_code(room.joinCode)
    assert room_by_code is not None
    assert room_by_code.roomId == room.roomId
    assert len(room.joinCode) == 6


@pytest.mark.asyncio
async def test_get_room_by_join_code_not_found(db_session, init_room):
    await init_room()

    with pytest.raises(ResourceNotFoundError):
        await room_repo.get_room_by_join_code("invalid_code")
