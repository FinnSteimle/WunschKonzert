from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain import FeedbackType, QueueEntryStatus
from services.vote_service import vote_queue_entry


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400():
    with pytest.raises(HTTPException) as exc:
        await vote_queue_entry("r1", "qe1", "u1", "sideways", session=AsyncMock())
    assert exc.value.status_code == 400
    assert "Invalid vote type" in exc.value.detail


@pytest.mark.asyncio
async def test_vote_replay_on_non_playing_raises_400():
    mock_entry = MagicMock()
    mock_entry.status = QueueEntryStatus.QUEUED
    mock_entry.roomId = "r1"

    with patch(
        "repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry
    ):
        with pytest.raises(HTTPException) as exc:
            await vote_queue_entry("r1", "qe1", "u1", "replay", session=AsyncMock())
        assert exc.value.status_code == 400
        assert "only be cast on the currently playing song" in exc.value.detail


@pytest.mark.asyncio
async def test_skip_threshold_math():
    """Test the 'strictly more than 50%' logic for different room sizes."""
    from services.vote_service import _handle_skip_vote

    async def run_math_test(member_count, skip_votes_count):
        mock_session = AsyncMock()
        mock_entry = MagicMock(status=QueueEntryStatus.PLAYING)

        with patch(
            "repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry
        ):
            mock_feedback = [
                MagicMock(type=FeedbackType.SKIP) for _ in range(skip_votes_count)
            ]
            with patch(
                "repositories.song_feedback_repo.get_song_feedback_by_queue_entry",
                return_value=mock_feedback,
            ):
                mock_members = [MagicMock() for _ in range(member_count)]
                with patch(
                    "repositories.membership_repo.get_room_active_memberships",
                    return_value=mock_members,
                ):
                    # Patching in services.vote_service because it's imported there
                    with patch(
                        "services.vote_service.advance_to_next", new_callable=AsyncMock
                    ) as mock_advance:
                        with patch(
                            "repositories.queue_entry_repo.update_queue_entry",
                            new_callable=AsyncMock,
                        ):
                            with patch(
                                "services.vote_service.refresh_room_state",
                                new_callable=AsyncMock,
                            ):
                                with patch(
                                    "services.vote_service.build_last_activity",
                                    new_callable=AsyncMock,
                                ):
                                    await _handle_skip_vote(
                                        "r1", "qe1", "u1", session=mock_session
                                    )
                                    return mock_advance.called

    assert await run_math_test(member_count=1, skip_votes_count=1) is True
    assert await run_math_test(member_count=1, skip_votes_count=0) is False
    assert await run_math_test(member_count=2, skip_votes_count=1) is False
    assert await run_math_test(member_count=2, skip_votes_count=2) is True
    assert await run_math_test(member_count=4, skip_votes_count=2) is False
    assert await run_math_test(member_count=4, skip_votes_count=3) is True


@pytest.mark.asyncio
async def test_vote_mutual_exclusivity():
    """Verify that an upvote removes a prior downvote."""
    mock_session = AsyncMock()
    mock_entry = MagicMock(roomId="r1", status=QueueEntryStatus.QUEUED)

    with patch(
        "repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry
    ):
        with patch(
            "repositories.song_feedback_repo.get_song_feedback", return_value=None
        ):
            with patch(
                "repositories.song_feedback_repo.delete_song_feedback",
                new_callable=AsyncMock,
            ) as mock_delete:
                # Patching internal logic
                with patch(
                    "services.vote_service._handle_vote_side_effects",
                    new_callable=AsyncMock,
                ):
                    await vote_queue_entry(
                        "r1", "qe1", "u1", "upvote", session=mock_session
                    )
                    mock_delete.assert_called_with(
                        "qe1",
                        "u1",
                        feedback_type=FeedbackType.DISLIKE,
                        session=mock_session,
                    )


@pytest.mark.asyncio
async def test_recalculate_and_refresh_ranking_logic():
    """Verify orderRank math: pos 1 with 1 upvote should be 0.99."""
    from services.vote_service import _recalculate_and_refresh

    mock_session = AsyncMock()
    mock_entry = MagicMock(position=1)

    with patch(
        "repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry
    ):
        mock_feedback = [MagicMock(type=FeedbackType.LIKE)]
        with patch(
            "repositories.song_feedback_repo.get_song_feedback_by_queue_entry",
            return_value=mock_feedback,
        ):
            with patch(
                "repositories.queue_entry_repo.update_queue_entry",
                new_callable=AsyncMock,
            ) as mock_update:
                # Patching in services.vote_service
                with patch(
                    "services.vote_service.refresh_room_state", new_callable=AsyncMock
                ):
                    await _recalculate_and_refresh(
                        "r1", "qe1", "event", session=mock_session
                    )
                    args, kwargs = mock_update.call_args
                    updates = args[1]
                    assert updates["voteScore"] == 1
                    assert pytest.approx(updates["orderRank"]) == 0.99
