from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.exceptions import ResourceNotFoundError
from services import playback_service

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_sync_playback_position_non_host():
    """Verify that sync_playback_position returns early if caller is not the host."""
    mock_session = AsyncMock()
    mock_room = MagicMock(hostedBy="host1")

    with patch("repositories.room_repo.get_room", return_value=mock_room):
        # user_id="user2" is NOT the host
        await playback_service.sync_playback_position(
            "r1", "user2", 1000, session=mock_session
        )

        # Verify it didn't proceed to get current playback session
        with patch(
            "repositories.playback_session_repo.get_current_playback_session"
        ) as mock_get_pb:
            await playback_service.sync_playback_position(
                "r1", "user2", 1000, session=mock_session
            )
            mock_get_pb.assert_not_called()


@pytest.mark.asyncio
async def test_set_playback_state_invalid_action():
    with pytest.raises(HTTPException) as exc:
        await playback_service.set_playback_state(
            "r1", "u1", "warp_speed", session=AsyncMock()
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_playback_state_room_not_found():
    mock_session = AsyncMock()
    with patch(
        "repositories.room_repo.get_room",
        side_effect=ResourceNotFoundError("Room not found"),
    ):
        with pytest.raises(HTTPException) as exc:
            await playback_service.set_playback_state(
                "r1", "u1", "pause", session=mock_session
            )
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_set_playback_state_not_host():
    mock_session = AsyncMock()
    mock_room = MagicMock(hostedBy="host1")
    with patch("repositories.room_repo.get_room", return_value=mock_room):
        with pytest.raises(HTTPException) as exc:
            await playback_service.set_playback_state(
                "r1", "user2", "pause", session=mock_session
            )
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_advance_to_next_no_current_session():
    """Verify advance_to_next when nothing is currently playing."""
    mock_session = AsyncMock()
    with (
        patch(
            "repositories.playback_session_repo.get_current_playback_session",
            return_value=None,
        ),
        patch("repositories.queue_entry_repo.get_next_queued_entry", return_value=None),
        patch(
            "services.playback_service.refresh_room_state", new_callable=AsyncMock
        ) as mock_refresh,
    ):
        await playback_service.advance_to_next("r1", session=mock_session)
        mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_advance_to_next_with_next_track():
    """Verify advance_to_next transition to a new track."""
    from models.domain import QueueEntryStatus

    mock_session = AsyncMock()
    mock_next = MagicMock(queueEntryId="qe2")

    with (
        patch(
            "repositories.playback_session_repo.get_current_playback_session",
            return_value=None,
        ),
        patch(
            "repositories.queue_entry_repo.get_next_queued_entry",
            return_value=mock_next,
        ),
        patch(
            "repositories.queue_entry_repo.update_queue_entry", new_callable=AsyncMock
        ) as mock_update_qe,
        patch(
            "repositories.song_feedback_repo.delete_song_feedback",
            new_callable=AsyncMock,
        ),
        patch(
            "repositories.playback_session_repo.create_playback_session",
            new_callable=AsyncMock,
        ),
        patch("services.playback_service.refresh_room_state", new_callable=AsyncMock),
    ):
        await playback_service.advance_to_next("r1", session=mock_session)

        # Verify next entry marked as playing
        mock_update_qe.assert_called_once()
        args, _ = mock_update_qe.call_args
        assert args[1]["status"] == QueueEntryStatus.PLAYING
