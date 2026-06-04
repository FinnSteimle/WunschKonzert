from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain import FeedbackType, QueueEntryStatus
from services.vote_service import (
    _handle_neutral_vote,
    _handle_replay_vote,
    _handle_skip_vote,
    _recalculate_and_refresh,
    _toggle_feedback,
    vote_queue_entry,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400():
    with pytest.raises(HTTPException) as exc:
        await vote_queue_entry(
            "r1", "qe1", "u1", "sideways", session=AsyncMock(spec=AsyncSession)
        )
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
            await vote_queue_entry(
                "r1", "qe1", "u1", "replay", session=AsyncMock(spec=AsyncSession)
            )
        assert exc.value.status_code == 400
        assert "only be cast on the currently playing song" in exc.value.detail


@pytest.mark.asyncio
async def test_skip_threshold_math():
    """Test the 'strictly more than 50%' logic for different room sizes."""

    async def run_math_test(member_count, skip_votes_count):
        mock_session = AsyncMock(spec=AsyncSession)
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
    mock_session = AsyncMock(spec=AsyncSession)
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
async def test_vote_replay_threshold_met():
    """Verify that reaching the replay threshold triggers track requeue."""

    mock_session = AsyncMock(spec=AsyncSession)
    mock_entry = MagicMock(trackId="t1", status=QueueEntryStatus.PLAYING)

    with (
        patch("repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry),
        patch(
            "repositories.song_feedback_repo.get_song_feedback_by_queue_entry",
            return_value=[MagicMock(type=FeedbackType.REPLAY)],
        ),
        patch(
            "repositories.membership_repo.get_room_active_memberships",
            return_value=[MagicMock()],
        ),
        patch(
            "repositories.track_repo.get_track", return_value=MagicMock(trackId="t1")
        ),
        patch("core.identifiers.generate_queue_entry_id", return_value="new_qe"),
        patch(
            "repositories.queue_entry_repo.create_queue_entry", new_callable=AsyncMock
        ) as mock_create,
        patch(
            "repositories.song_feedback_repo.delete_song_feedback",
            new_callable=AsyncMock,
        ) as mock_delete,
        patch("services.vote_service.refresh_room_state", new_callable=AsyncMock),
    ):
        await _handle_replay_vote("r1", "qe1", "u1", session=mock_session)

        # Verify new entry created with high voteScore and negative orderRank
        args, _ = mock_create.call_args
        assert args[0]["voteScore"] == 9999
        assert args[0]["orderRank"] == -1.0
        assert args[0]["trackId"] == "t1"

        # Verify replay feedback deleted
        mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_neutral_vote():
    """Verify that neutral vote clears both like and dislike feedback."""

    mock_session = AsyncMock(spec=AsyncSession)
    with (
        patch(
            "repositories.song_feedback_repo.delete_song_feedback",
            new_callable=AsyncMock,
        ) as mock_delete,
        patch("services.vote_service.build_last_activity", new_callable=AsyncMock),
        patch("services.vote_service._recalculate_and_refresh", new_callable=AsyncMock),
    ):
        await _handle_neutral_vote("r1", "qe1", "u1", session=mock_session)

        assert mock_delete.call_count == 2
        # Verify it attempted to delete both LIKE and DISLIKE
        calls = mock_delete.call_args_list
        types = [call.kwargs["feedback_type"] for call in calls]
        assert FeedbackType.LIKE in types
        assert FeedbackType.DISLIKE in types


@pytest.mark.asyncio
async def test_vote_toggle_logic():
    """Verify that voting for the same thing twice toggles (removes) it."""

    mock_session = AsyncMock(spec=AsyncSession)
    # Mocking existing feedback to trigger toggle removal
    with (
        patch(
            "repositories.song_feedback_repo.get_song_feedback",
            return_value=MagicMock(),
        ),
        patch(
            "repositories.song_feedback_repo.delete_song_feedback",
            new_callable=AsyncMock,
        ) as mock_delete,
        patch("services.vote_service._recalculate_and_refresh", new_callable=AsyncMock),
    ):
        result = await _toggle_feedback(
            "r1", "qe1", "u1", FeedbackType.LIKE, session=mock_session
        )
        assert result is not None
        mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_recalculate_and_refresh_no_entry():
    """Verify that recalculate_and_refresh handles missing entry gracefully."""

    mock_session = AsyncMock(spec=AsyncSession)
    with (
        patch("repositories.queue_entry_repo.get_queue_entry", return_value=None),
        patch(
            "services.vote_service.refresh_room_state", new_callable=AsyncMock
        ) as mock_refresh,
    ):
        await _recalculate_and_refresh("r1", "qe1", "event", session=mock_session)
        mock_refresh.assert_called_once()
