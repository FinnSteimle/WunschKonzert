from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain import PlaybackState
from services.playback_service import _determine_playback_updates, set_playback_state


def test_determine_playback_updates_pause():
    updates = _determine_playback_updates("pause", 120)
    assert updates["state"] == PlaybackState.PAUSED
    assert isinstance(updates["pausedAt"], datetime)
    assert updates["elapsedTime"] == 120


def test_determine_playback_updates_resume():
    updates = _determine_playback_updates("resume", 150)
    assert updates["state"] == PlaybackState.PLAYING
    assert updates["pausedAt"] is None
    assert updates["elapsedTime"] == 150


def test_determine_playback_updates_stop():
    updates = _determine_playback_updates("stop", None)
    assert updates["state"] == PlaybackState.STOPPED
    assert isinstance(updates["pausedAt"], datetime)
    assert "elapsedTime" not in updates


@pytest.mark.asyncio
async def test_set_playback_state_invalid_action_raises_400():
    with pytest.raises(HTTPException) as exc:
        await set_playback_state("r1", "host", "rewind", session=AsyncMock())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_playback_state_non_host_raises_403():
    # Return a plain mock with the hostedBy attribute
    mock_room = MagicMock()
    mock_room.hostedBy = "real_host"

    with patch("repositories.room_repo.get_room", return_value=mock_room):
        with pytest.raises(HTTPException) as exc:
            await set_playback_state("r1", "fake_host", "pause", session=AsyncMock())
        assert exc.value.status_code == 403
        assert "Only the host" in exc.value.detail


@pytest.mark.asyncio
async def test_set_playback_state_resume_mismatch_ignores_position():
    """Verify that if we resume a DIFFERENT track, the provided position is ignored."""
    mock_session = AsyncMock()

    mock_room = MagicMock()
    mock_room.hostedBy = "host1"

    mock_playback = MagicMock()
    mock_playback.playbackSessionId = "ps1"
    mock_playback.queueEntryId = "song_a"

    with patch("repositories.room_repo.get_room", return_value=mock_room):
        with patch(
            "repositories.playback_session_repo.get_current_playback_session",
            return_value=mock_playback,
        ):
            with patch(
                "repositories.playback_session_repo.update_playback_session",
                new_callable=AsyncMock,
            ) as mock_update:
                # Patch in services.playback_service because they are imported there
                with patch(
                    "services.playback_service.refresh_room_state",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "services.playback_service.build_last_activity",
                        new_callable=AsyncMock,
                    ):
                        # Resuming song_b with position 30s, but currently playing song_a
                        await set_playback_state(
                            "r1",
                            "host1",
                            "resume",
                            position_ms=30000,
                            queue_entry_id="song_b",
                            session=mock_session,
                        )

                        # Verify updates: elapsedTime should NOT be in the update dict
                        # args[1] is the 'updates' dict in update_playback_session(id, updates, session)
                        args, kwargs = mock_update.call_args
                        updates = args[1]
                        assert "elapsedTime" not in updates
