import uuid

import pytest
from fastapi import HTTPException

from models import domain
from repositories import (
    playback_session_repo,
    queue_entry_repo,
    track_repo,
    user_repo,
)
from services import playback_service, queue_service, room_state_service

pytestmark = pytest.mark.integration


async def _add_track_to_queue(room_id: str, user_id: str) -> str:
    """Helper: add one track to a room, return its queueEntryId."""
    track_id = str(uuid.uuid4())
    await queue_service.add_to_queue(
        room_id,
        {
            "trackId": track_id,
            "providerTrackId": f"spotify:track:{track_id[:8]}",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        },
        user_id,
    )
    entries = await queue_entry_repo.get_queue_entries(room_id)
    return entries[0].queueEntryId


@pytest.mark.asyncio
async def test_playback_non_host_raises_403(db_session, init_room):
    room = await init_room()
    other_user = str(uuid.uuid4())
    await user_repo.create_user(other_user, "guest")

    with pytest.raises(HTTPException) as exc_info:
        await playback_service.set_playback_state(room.roomId, other_user, "pause")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_playback_invalid_action_raises_400(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await playback_service.set_playback_state(room.roomId, room.hostedBy, "rewind")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_playback_pause_and_resume(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    await playback_service.set_playback_state(room.roomId, room.hostedBy, "pause")
    session = await playback_session_repo.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.PAUSED

    await playback_service.set_playback_state(room.roomId, room.hostedBy, "resume")
    session = await playback_session_repo.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.PLAYING


@pytest.mark.asyncio
async def test_playback_stop(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    await playback_service.set_playback_state(room.roomId, room.hostedBy, "stop")
    session = await playback_session_repo.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.STOPPED


@pytest.mark.asyncio
async def test_playback_advance_moves_to_next_track(db_session, init_room):
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

    state = await playback_service.set_playback_state(
        room.roomId, room.hostedBy, "advance"
    )

    playing = [e for e in state["queue"] if e["status"] == "playing"]
    assert len(playing) == 1
    assert playing[0]["track"]["title"] == "Second"


@pytest.mark.asyncio
async def test_playback_no_session_resume_creates_session(db_session, init_room):
    """resume with no existing session picks the first queued entry."""
    room = await init_room()
    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "sp:x",
            "title": "T",
            "artist": "A",
            "album": "",
            "duration": 100,
            "coverUrl": "",
            "deepLink": "",
        }
    )
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": f"QENTRY{uuid.uuid4().hex[:8].upper()}",
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": room.hostedBy,
            "position": 1,
            "status": domain.QueueEntryStatus.QUEUED,
            "voteScore": 0,
            "orderRank": 1.0,
        }
    )

    await playback_service.set_playback_state(room.roomId, room.hostedBy, "resume")
    session = await playback_session_repo.get_current_playback_session(room.roomId)
    assert session is not None
    assert session.state == domain.PlaybackState.PLAYING


@pytest.mark.asyncio
async def test_sync_playback_position_updates_cache(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    # First song starts paused, need to resume before syncing position
    await playback_service.set_playback_state(room.roomId, room.hostedBy, "resume")

    # Seed cache
    await room_state_service.refresh_room_state(room.roomId)

    await playback_service.sync_playback_position(room.roomId, room.hostedBy, 30_000)

    cached = room_state_service.room_state_cache.get(room.roomId)
    assert cached is not None
    assert cached["playback"]["positionMs"] == 30_000


@pytest.mark.asyncio
async def test_sync_playback_position_non_host_is_noop(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)
    await room_state_service.refresh_room_state(room.roomId)

    other = str(uuid.uuid4())
    await user_repo.create_user(other, "other")
    await playback_service.sync_playback_position(room.roomId, other, 99_000)

    cached = room_state_service.room_state_cache.get(room.roomId)
    # Position should NOT have been updated to 99_000
    assert cached["playback"]["positionMs"] != 99_000
