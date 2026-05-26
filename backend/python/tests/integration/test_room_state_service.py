import uuid
from typing import cast

import pytest

from repositories import (
    membership_repo,
    queue_entry_repo,
    user_repo,
)
from services import playback_service, queue_service, room_state_service

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_refresh_room_state_success(db_session, init_room):
    room = await init_room()
    state = await room_state_service.refresh_room_state(room.roomId)
    assert state["room"]["roomId"] == room.roomId
    assert state["room"]["name"] == room.name
    assert state["host"]["userId"] == room.hostedBy


@pytest.mark.asyncio
async def test_get_song_history_success(db_session, init_room):
    room = await init_room()
    state = await room_state_service.get_song_history(room.roomId)
    assert "history" in state
    assert state["lastEvent"]["type"] == "history_updated"


@pytest.mark.asyncio
async def test_user_list_exclude_users_who_left(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())

    await user_repo.create_user(guest_id, "guest")
    await membership_repo.create_room_membership(guest_id, room.roomId)
    await membership_repo.leave_room(guest_id, room.roomId)

    state = await room_state_service.refresh_room_state(room.roomId)
    participants = cast(list, state["users"])
    user_ids = [u["user"]["userId"] for u in participants]
    assert guest_id not in user_ids


@pytest.mark.asyncio
async def test_user_list_host_not_duplicated(db_session, init_room):
    room = await init_room()

    state = await room_state_service.refresh_room_state(room.roomId)
    participants = cast(list, state["users"])
    user_ids = [u["user"]["userId"] for u in participants]

    assert user_ids.count(room.hostedBy) == 1


@pytest.mark.asyncio
async def test_playback_state_mapping_in_room_state(db_session, init_room):
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

    song_a = await _enqueue("A")
    await _enqueue("B")

    playing_state = await room_state_service.refresh_room_state(room.roomId)
    playback = cast(dict, playing_state["playback"])
    assert playback["state"] == "paused"  # First song starts paused, host must resume
    assert playback["currentQueueEntryId"] == song_a

    # After stop, currentQueueEntryId must be None
    await playback_service.set_playback_state(room.roomId, room.hostedBy, "stop")
    stopped_state = await room_state_service.refresh_room_state(room.roomId)
    playback = cast(dict, stopped_state["playback"])
    assert playback["state"] == "stopped"
    assert playback["currentQueueEntryId"] is None
