from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain import FeedbackType, QueueEntryStatus, RoomStatus
from services.queue_service import add_to_queue, remove_queue_entry


@pytest.mark.asyncio
async def test_add_to_queue_inactive_room_raises_400():
    """Verify we cannot add songs to a deleted or archived room."""
    mock_session = AsyncMock()

    # Mock a room that is DELETED
    mock_room = MagicMock()
    mock_room.status = RoomStatus.DELETED

    with patch("services.queue_service.room_repo.get_room", return_value=mock_room):
        with pytest.raises(HTTPException) as exc:
            await add_to_queue("r1", {"trackId": "t1"}, "u1", session=mock_session)
        assert exc.value.status_code == 400
        assert "not active" in exc.value.detail


@pytest.mark.asyncio
async def test_remove_queue_entry_host_permission():
    """Verify that the host can remove any song directly (no vote needed)."""
    mock_session = AsyncMock()

    # Mock room where 'host1' is the host
    mock_room = MagicMock(hostedBy="host1")
    # Mock a queue entry added by someone else ('user2')
    mock_entry = MagicMock(roomId="r1", addedBy="user2", status=QueueEntryStatus.QUEUED)

    with patch("services.queue_service.room_repo.get_room", return_value=mock_room):
        with patch(
            "services.queue_service.queue_entry_repo.get_queue_entry",
            return_value=mock_entry,
        ):
            with patch(
                "services.queue_service.queue_entry_repo.update_queue_entry",
                new_callable=AsyncMock,
            ) as mock_update:
                with patch(
                    "services.queue_service.refresh_room_state", new_callable=AsyncMock
                ):
                    with patch(
                        "services.queue_service.build_last_activity",
                        new_callable=AsyncMock,
                    ):
                        # Host ('host1') tries to remove 'user2's song
                        await remove_queue_entry(
                            "r1", "qe1", "host1", session=mock_session
                        )

                        # Success: it should have called update_queue_entry to set status to REMOVED
                        args, kwargs = mock_update.call_args
                        assert args[1]["status"] == QueueEntryStatus.REMOVED


@pytest.mark.asyncio
async def test_remove_queue_entry_adder_with_upvotes_falls_back_to_vote():
    """Verify that if an adder tries to remove their song but it has upvotes, it triggers a skip vote."""
    mock_session = AsyncMock()

    mock_room = MagicMock(hostedBy="host1")
    # 'user2' added this song
    mock_entry = MagicMock(roomId="r1", addedBy="user2", status=QueueEntryStatus.QUEUED)

    with patch("services.queue_service.room_repo.get_room", return_value=mock_room):
        with patch(
            "services.queue_service.queue_entry_repo.get_queue_entry",
            return_value=mock_entry,
        ):
            # Mock that the song HAS an upvote
            mock_feedback = [MagicMock(type=FeedbackType.LIKE)]
            with patch(
                "services.queue_service.song_feedback_repo.get_song_feedback_by_queue_entry",
                return_value=mock_feedback,
            ):
                # This is the "Social Fallback": instead of updating the repo, it calls vote_queue_entry
                with patch(
                    "services.queue_service.vote_queue_entry", new_callable=AsyncMock
                ) as mock_vote:
                    # User2 tries to remove their own song
                    await remove_queue_entry("r1", "qe1", "user2", session=mock_session)

                    # Verify: it didn't remove it directly, it cast a "skip" vote instead
                    mock_vote.assert_called_with(
                        "r1", "qe1", "user2", "skip", session=mock_session
                    )


@pytest.mark.asyncio
async def test_remove_queue_entry_stranger_falls_back_to_vote():
    """Verify that a random user cannot remove someone else's song directly."""
    mock_session = AsyncMock()

    mock_room = MagicMock(hostedBy="host1")
    # 'user2' added this song, but 'stranger' is calling the function
    mock_entry = MagicMock(roomId="r1", addedBy="user2", status=QueueEntryStatus.QUEUED)

    with patch("services.queue_service.room_repo.get_room", return_value=mock_room):
        with patch(
            "services.queue_service.queue_entry_repo.get_queue_entry",
            return_value=mock_entry,
        ):
            with patch(
                "services.queue_service.vote_queue_entry", new_callable=AsyncMock
            ) as mock_vote:
                await remove_queue_entry("r1", "qe1", "stranger", session=mock_session)

                # Should fallback to skip vote
                mock_vote.assert_called_with(
                    "r1", "qe1", "stranger", "skip", session=mock_session
                )
