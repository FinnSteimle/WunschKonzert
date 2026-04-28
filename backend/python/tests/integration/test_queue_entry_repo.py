import uuid

import pytest

from models.domain import QueueEntryStatus
from repositories import queue_entry_repo, track_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_queue_entry(db_session, init_room):
    """Test creating a new queue entry"""
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

    queue_entry_data = {
        "queueEntryId": str(uuid.uuid4()),
        "roomId": room.roomId,
        "trackId": track_id,
        "addedBy": host_id,
        "position": 1,
        "status": QueueEntryStatus.QUEUED,
        "voteScore": 0,
    }

    entry = await queue_entry_repo.create_queue_entry(queue_entry_data)

    assert entry.roomId == room.roomId
    assert entry.trackId == track_id
    assert entry.position == 1
    assert entry.status == QueueEntryStatus.QUEUED


@pytest.mark.asyncio
async def test_get_queue_entries(db_session, init_room):
    """Test retrieving all queue entries for a room"""
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

    # Create multiple queue entries
    for i in range(3):
        await queue_entry_repo.create_queue_entry(
            {
                "queueEntryId": str(uuid.uuid4()),
                "roomId": room.roomId,
                "trackId": track_id,
                "addedBy": host_id,
                "position": i + 1,
            }
        )

    entries = await queue_entry_repo.get_queue_entries(room.roomId)
    assert len(entries) == 3
    assert entries[0].position == 1
    assert entries[2].position == 3


@pytest.mark.asyncio
async def test_update_queue_entry(db_session, init_room):
    """Test updating a queue entry"""
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

    entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
            "voteScore": 0,
        }
    )

    updated_entry = await queue_entry_repo.update_queue_entry(
        entry_id, {"voteScore": 5, "status": QueueEntryStatus.PLAYING}
    )

    assert updated_entry.voteScore == 5
    assert updated_entry.status == QueueEntryStatus.PLAYING


@pytest.mark.asyncio
async def test_get_max_queue_position(db_session, init_room):
    """Test getting the maximum queue position"""
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

    # Create entries with different positions
    for position in [1, 3, 5]:
        await queue_entry_repo.create_queue_entry(
            {
                "queueEntryId": str(uuid.uuid4()),
                "roomId": room.roomId,
                "trackId": track_id,
                "addedBy": host_id,
                "position": position,
            }
        )

    max_position = await queue_entry_repo.get_max_queue_position(room.roomId)
    assert max_position == 5


@pytest.mark.asyncio
async def test_get_next_queued_entry(db_session, init_room):
    """Test getting the next queued entry by vote score"""
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

    # Create entries with different vote scores
    entry1_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": entry1_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
            "voteScore": 3,
            "status": QueueEntryStatus.QUEUED,
        }
    )

    entry2_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": entry2_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 2,
            "voteScore": 10,
            "status": QueueEntryStatus.QUEUED,
        }
    )

    next_entry = await queue_entry_repo.get_next_queued_entry(room.roomId)
    assert next_entry is not None
    assert next_entry.queueEntryId == entry2_id
    assert next_entry.voteScore == 10
