import uuid
from typing import cast

import pytest
from fastapi import HTTPException

from models import domain
from repositories import (
    membership_repo,
    queue_entry_repo,
    user_repo,
)
from services import queue_service, room_service, room_state_service, vote_service

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_queue_add_remove(db_session, init_room):
    room = await init_room()
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "queue_guest")
    await membership_repo.create_room_membership(user_id, room.roomId)

    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:test123",
        "title": "Fireworks",
        "artist": "Katy Perry",
        "album": "Teenage Dream",
        "duration": 228,
        "coverUrl": "",
        "deepLink": "",
    }

    await queue_service.add_to_queue(room.roomId, track_data, user_id)
    entries = await queue_entry_repo.get_queue_entries(room.roomId)
    assert len(entries) == 1
    item = entries[0]
    assert item.trackId == track_id
    assert item.addedBy == user_id
    assert item.status == domain.QueueEntryStatus.PLAYING

    await queue_service.remove_queue_entry(room.roomId, item.queueEntryId, user_id)
    entries_after = await queue_entry_repo.get_queue_entries(room.roomId)
    assert all(e.status == domain.QueueEntryStatus.REMOVED for e in entries_after)


@pytest.mark.asyncio
async def test_add_to_queue_room_not_found(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await queue_service.add_to_queue(
            str(uuid.uuid4()),
            {
                "trackId": str(uuid.uuid4()),
                "providerTrackId": "x",
                "title": "T",
                "artist": "A",
                "album": "",
                "duration": 0,
                "coverUrl": "",
                "deepLink": "",
            },
            str(uuid.uuid4()),
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_to_queue_inactive_room(db_session, init_room):
    room = await init_room()
    await room_service.delete_room(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await queue_service.add_to_queue(
            room.roomId,
            {
                "trackId": str(uuid.uuid4()),
                "providerTrackId": "x",
                "title": "T",
                "artist": "A",
                "album": "",
                "duration": 0,
                "coverUrl": "",
                "deepLink": "",
            },
            room.hostedBy,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_add_to_queue_duplicate_track_raises_409(db_session, init_room):
    room = await init_room()
    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:dup",
        "title": "Dup",
        "artist": "A",
        "album": "",
        "duration": 200,
        "coverUrl": "",
        "deepLink": "",
    }
    await queue_service.add_to_queue(room.roomId, track_data, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await queue_service.add_to_queue(room.roomId, track_data, room.hostedBy)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_add_to_queue_allows_readding_track_after_played(db_session, init_room):
    room = await init_room()
    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:played",
        "title": "Replay Me",
        "artist": "A",
        "album": "",
        "duration": 200,
        "coverUrl": "",
        "deepLink": "",
    }

    await queue_service.add_to_queue(room.roomId, track_data, room.hostedBy)
    first_entry = (await queue_entry_repo.get_queue_entries(room.roomId))[0]
    await queue_entry_repo.update_queue_entry(
        first_entry.queueEntryId, {"status": domain.QueueEntryStatus.PLAYED}
    )

    await queue_service.add_to_queue(room.roomId, track_data, room.hostedBy)
    entries = await queue_entry_repo.get_queue_entries(room.roomId)

    assert len(entries) == 2
    assert sum(1 for entry in entries if entry.trackId == track_id) == 2


@pytest.mark.asyncio
async def test_add_to_queue_second_track_is_queued_not_playing(db_session, init_room):
    room = await init_room()

    async def _track(title: str) -> dict:
        return {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "A",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }

    await queue_service.add_to_queue(room.roomId, await _track("First"), room.hostedBy)
    await queue_service.add_to_queue(room.roomId, await _track("Second"), room.hostedBy)

    entries = await queue_entry_repo.get_queue_entries(room.roomId)
    statuses = {e.status for e in entries}
    assert domain.QueueEntryStatus.PLAYING in statuses
    assert domain.QueueEntryStatus.QUEUED in statuses


@pytest.mark.asyncio
async def test_queue_sort_order(db_session, init_room):
    room = await init_room()

    async def _enqueue(title: str) -> str:
        track = {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }
        await queue_service.add_to_queue(room.roomId, track, room.hostedBy)
        entry = await queue_entry_repo.get_queue_entry_by_track(
            room.roomId, track["trackId"]
        )
        assert entry is not None
        return entry.queueEntryId

    async def _vote(entry_id: str, vote: str, count: int = 1) -> None:
        for _ in range(count):
            uid = str(uuid.uuid4())
            await user_repo.create_user(uid, uid)
            await vote_service.vote_queue_entry(room.roomId, entry_id, uid, vote)

    # C is added first → gets status=playing, always sorts first
    await _enqueue("C")
    b = await _enqueue("B")
    e = await _enqueue("E")
    await _enqueue("D")
    a = await _enqueue("A")

    await _vote(a, "upvote", count=2)  # score +2
    await _vote(b, "upvote", count=1)  # score +1
    # d: no votes                        # score  0
    await _vote(e, "downvote", count=1)  # score -1

    room_state = await room_state_service.refresh_room_state(room.roomId)

    titles = [e["track"]["title"] for e in cast(list[dict], room_state["queue"])]
    assert titles == ["C", "A", "B", "D", "E"]
