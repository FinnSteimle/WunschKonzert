import uuid

import pytest

from core.exceptions import ResourceNotFoundError
from models.domain import QueueEntryStatus
from repositories import (
    music_provider_repo,
    queue_entry_repo,
    room_repo,
    track_repo,
    user_repo,
)

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


@pytest.mark.asyncio
async def test_get_room_with_full_state_filters_removed_queue_entries(
    db_session, init_room
):
    room = await init_room()
    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:test",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    entry = await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": str(uuid.uuid4()),
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": room.hostedBy,
            "position": 1,
            "status": QueueEntryStatus.PLAYING,
            "voteScore": 0,
        }
    )

    await queue_entry_repo.update_queue_entry(
        entry.queueEntryId, {"status": QueueEntryStatus.REMOVED}, session=db_session
    )
    await db_session.commit()

    full_state = await room_repo.get_room_with_full_state(room.roomId)
    assert full_state.queue_entries == []
