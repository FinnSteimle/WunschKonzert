import uuid

import pytest

from models.domain import PlaybackState, QueueEntryStatus
from repositories import playback_session_repo, queue_entry_repo, track_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_playback_session(db_session, init_room):
    """Test creating a new playback session"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
            "status": QueueEntryStatus.PLAYING,
        }
    )

    playback_data = {
        "playbackSessionId": str(uuid.uuid4()),
        "roomId": room.roomId,
        "queueEntryId": queue_entry_id,
        "elapsedTime": 0,
        "state": PlaybackState.PLAYING,
    }

    session = await playback_session_repo.create_playback_session(playback_data)

    assert session.roomId == room.roomId
    assert session.queueEntryId == queue_entry_id
    assert session.state == PlaybackState.PLAYING


@pytest.mark.asyncio
async def test_get_current_playback_session(db_session, init_room):
    """Test retrieving the current playback session"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
        }
    )

    session_id = str(uuid.uuid4())
    await playback_session_repo.create_playback_session(
        {
            "playbackSessionId": session_id,
            "roomId": room.roomId,
            "queueEntryId": queue_entry_id,
            "state": PlaybackState.PLAYING,
        }
    )

    current_session = await playback_session_repo.get_current_playback_session(
        room.roomId
    )

    assert current_session is not None
    assert current_session.playbackSessionId == session_id


@pytest.mark.asyncio
async def test_update_playback_session(db_session, init_room):
    """Test updating a playback session"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
        }
    )

    session_id = str(uuid.uuid4())
    await playback_session_repo.create_playback_session(
        {
            "playbackSessionId": session_id,
            "roomId": room.roomId,
            "queueEntryId": queue_entry_id,
            "elapsedTime": 0,
            "state": PlaybackState.PLAYING,
        }
    )

    updated_session = await playback_session_repo.update_playback_session(
        session_id, {"elapsedTime": 30, "state": PlaybackState.PAUSED}
    )

    assert updated_session.elapsedTime == 30
    assert updated_session.state == PlaybackState.PAUSED
