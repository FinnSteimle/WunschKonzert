import uuid
from typing import cast

import pytest

from models import domain
from repositories import (
    queue_entry_repo,
)
from services import room_service

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_playback_history_tracking(db_session, init_room):
    """Test that played songs are correctly added to history and returned in room state."""
    room = await init_room()

    async def _track(title: str) -> dict:
        return {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title[:8]}",
            "title": title,
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180,
            "coverUrl": "http://example.com/cover.jpg",
            "deepLink": "spotify:track:123",
        }

    # Add two tracks
    await room_service.add_to_queue(room.roomId, await _track("First Song"), room.hostedBy)
    await room_service.add_to_queue(room.roomId, await _track("Second Song"), room.hostedBy)

    # Initial state: 'First Song' is playing (since it was first), 'Second Song' is queued
    state = await room_service.refresh_room_state(room.roomId)
    assert len(state["history"]) == 0
    assert any(e["track"]["title"] == "First Song" and e["status"] == "playing" for e in state["queue"])

    # Advance to next track: 'First Song' should move to history
    await room_service.set_playback_state(room.roomId, room.hostedBy, "advance")

    state = await room_service.refresh_room_state(room.roomId)
    history = cast(list[dict], state["history"])
    assert len(history) == 1
    assert history[0]["track"]["title"] == "First Song"
    assert any(e["track"]["title"] == "Second Song" and e["status"] == "playing" for e in state["queue"])

    # Advance again: 'Second Song' should move to history
    await room_service.set_playback_state(room.roomId, room.hostedBy, "advance")

    state = await room_service.refresh_room_state(room.roomId)
    history = cast(list[dict], state["history"])
    assert len(history) == 2
    assert history[0]["track"]["title"] == "Second Song"
    assert history[1]["track"]["title"] == "First Song"


@pytest.mark.asyncio
async def test_get_song_history_event(db_session, init_room):
    """Test that the get_song_history service method triggers the correct event."""
    room = await init_room()
    
    # Just verify it returns the state with the right lastEvent
    state = await room_service.get_song_history(room.roomId)
    assert "history" in state
    assert state["lastEvent"]["type"] == "history_updated"
