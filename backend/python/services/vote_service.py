import math
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.membership_repo as membership_repo
import repositories.queue_entry_repo as queue_entry_repo
import repositories.song_feedback_repo as song_feedback_repo
import repositories.track_repo as track_repo
from core import identifiers
from core.database import get_session_factory
from models.domain import FeedbackType, QueueEntryStatus
from services.playback_service import advance_to_next
from services.room_state_service import (
    build_last_activity,
    refresh_room_state,
    ui_to_feedback,
)


async def _handle_neutral_vote(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    session: AsyncSession,
) -> dict[str, object]:
    await song_feedback_repo.delete_song_feedback(
        queue_entry_id,
        user_id,
        feedback_type=FeedbackType.LIKE,
        session=session,
    )
    await song_feedback_repo.delete_song_feedback(
        queue_entry_id,
        user_id,
        feedback_type=FeedbackType.DISLIKE,
        session=session,
    )
    activity = await build_last_activity(
        "vote_cleared", user_id, session, queue_entry_id=queue_entry_id
    )
    return await _recalculate_and_refresh(
        room_id,
        queue_entry_id,
        "vote_updated",
        session=session,
        last_activity=activity,
    )


async def _toggle_feedback(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    feedback_type: FeedbackType,
    session: AsyncSession,
) -> dict[str, object] | None:
    existing = await song_feedback_repo.get_song_feedback(
        queue_entry_id, user_id, feedback_type=feedback_type, session=session
    )
    if existing:
        await song_feedback_repo.delete_song_feedback(
            queue_entry_id, user_id, feedback_type=feedback_type, session=session
        )
        return await _recalculate_and_refresh(
            room_id,
            queue_entry_id,
            "vote_updated",
            session=session,
            last_activity=await build_last_activity(
                "vote_cleared", user_id, session, queue_entry_id=queue_entry_id
            ),
        )
    return None


async def vote_queue_entry(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    vote_type: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await vote_queue_entry(
                room_id, queue_entry_id, user_id, vote_type, session=new_session
            )
            await new_session.commit()
            return result

    if vote_type not in {"upvote", "downvote", "neutral", "skip", "replay"}:
        raise HTTPException(status_code=400, detail="Invalid vote type")

    # Get queue entry
    queue_entry = await queue_entry_repo.get_queue_entry(
        queue_entry_id, session=session
    )
    if not queue_entry or queue_entry.roomId != room_id:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if vote_type == "replay" and queue_entry.status != QueueEntryStatus.PLAYING:
        raise HTTPException(
            status_code=400,
            detail="Replay votes can only be cast on the currently playing song",
        )

    if vote_type == "neutral":
        return await _handle_neutral_vote(room_id, queue_entry_id, user_id, session)

    mapped_type = ui_to_feedback(vote_type)
    if not mapped_type:
        raise HTTPException(status_code=400, detail="Invalid vote type")

    activity_type = {
        FeedbackType.LIKE: "up_vote",
        FeedbackType.DISLIKE: "down_vote",
        FeedbackType.SKIP: "skip_vote",
        FeedbackType.REPLAY: "replay_vote",
    }[mapped_type]

    toggle_result = await _toggle_feedback(
        room_id, queue_entry_id, user_id, mapped_type, session
    )
    if toggle_result:
        return toggle_result

    await _handle_mutual_exclusivity(queue_entry_id, user_id, mapped_type, session)

    # Create/Update the vote
    await song_feedback_repo.create_or_update_song_feedback(
        {
            "queueEntryId": queue_entry_id,
            "userId": user_id,
            "type": mapped_type,
            "votedAt": datetime.now(UTC).replace(tzinfo=None),
        },
        session=session,
    )

    return await _handle_vote_side_effects(
        room_id,
        queue_entry_id,
        user_id,
        mapped_type,
        activity_type,
        session,
    )


async def _handle_mutual_exclusivity(
    queue_entry_id: str,
    user_id: str,
    mapped_type: FeedbackType,
    session: AsyncSession,
) -> None:
    """Handle Mutual Exclusivity for Upvote/Downvote."""
    if mapped_type in {FeedbackType.LIKE, FeedbackType.DISLIKE}:
        other_type = (
            FeedbackType.DISLIKE
            if mapped_type == FeedbackType.LIKE
            else FeedbackType.LIKE
        )
        await song_feedback_repo.delete_song_feedback(
            queue_entry_id, user_id, feedback_type=other_type, session=session
        )


async def _handle_vote_side_effects(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    mapped_type: FeedbackType,
    activity_type: str,
    session: AsyncSession,
) -> dict[str, object]:
    """Handle side effects like skip/replay thresholds or just recalculate."""
    if mapped_type == FeedbackType.SKIP:
        return await _handle_skip_vote(
            room_id, queue_entry_id, user_id, session=session
        )

    if mapped_type == FeedbackType.REPLAY:
        return await _handle_replay_vote(
            room_id, queue_entry_id, user_id, session=session
        )

    return await _recalculate_and_refresh(
        room_id,
        queue_entry_id,
        "vote_updated",
        session=session,
        last_activity=await build_last_activity(
            activity_type, user_id, session, queue_entry_id=queue_entry_id
        ),
    )


async def _handle_skip_vote(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    """Check if skip threshold is met and advance if necessary."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await _handle_skip_vote(
                room_id, queue_entry_id, user_id, session=new_session
            )
            await new_session.commit()
            return result

    queue_entry = await queue_entry_repo.get_queue_entry(
        queue_entry_id, session=session
    )
    if not queue_entry:
        return {"success": True, "message": "Vote updated"}

    feedback_list = await song_feedback_repo.get_song_feedback_by_queue_entry(
        queue_entry_id, session=session
    )
    skip_count = sum(1 for f in feedback_list if f.type == FeedbackType.SKIP)
    active_members = await membership_repo.get_room_active_memberships(
        room_id, session=session
    )

    # All active members are eligible — strictly more than 50% triggers skip/remove.
    eligible = max(1, len(active_members))
    required = math.floor(eligible / 2) + 1

    if skip_count >= required:
        if queue_entry.status == QueueEntryStatus.PLAYING:
            await advance_to_next(room_id, session=session)
        await queue_entry_repo.update_queue_entry(
            queue_entry_id, {"status": QueueEntryStatus.REMOVED}, session=session
        )
        threshold_activity = await build_last_activity(
            "skip_threshold_met", user_id, session, queue_entry_id=queue_entry_id
        )
        return await refresh_room_state(
            room_id,
            "queue_updated",
            session=session,
            last_activity=threshold_activity,
        )

    return await _recalculate_and_refresh(
        room_id,
        queue_entry_id,
        "vote_updated",
        session=session,
        last_activity=await build_last_activity(
            "skip_vote", user_id, session, queue_entry_id=queue_entry_id
        ),
    )


async def _handle_replay_vote(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    """Check if replay threshold is met and requeue if necessary."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await _handle_replay_vote(
                room_id, queue_entry_id, user_id, session=new_session
            )
            await new_session.commit()
            return result

    queue_entry = await queue_entry_repo.get_queue_entry(
        queue_entry_id, session=session
    )
    if not queue_entry:
        return {"success": True, "message": "Vote updated"}

    feedback_list = await song_feedback_repo.get_song_feedback_by_queue_entry(
        queue_entry_id, session=session
    )
    replay_count = sum(1 for f in feedback_list if f.type == FeedbackType.REPLAY)
    active_members = await membership_repo.get_room_active_memberships(
        room_id, session=session
    )

    eligible = max(1, len(active_members))
    required = math.floor(eligible / 2) + 1

    if replay_count >= required:
        # Threshold reached, requeue the track to play next
        track = await track_repo.get_track(queue_entry.trackId, session=session)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        new_queue_entry_id = identifiers.generate_queue_entry_id()
        await queue_entry_repo.create_queue_entry(
            {
                "queueEntryId": new_queue_entry_id,
                "roomId": room_id,
                "trackId": track.trackId,
                "addedBy": user_id,
                "position": 0,
                "status": QueueEntryStatus.QUEUED,
                "voteScore": 9999,
                "orderRank": -1.0,
            },
            session=session,
        )

        await song_feedback_repo.delete_song_feedback(
            queue_entry_id, feedback_type=FeedbackType.REPLAY, session=session
        )
        threshold_activity = await build_last_activity(
            "replay_threshold_met", user_id, session, queue_entry_id=queue_entry_id
        )
        return await refresh_room_state(
            room_id,
            "vote_updated",
            session=session,
            last_activity=threshold_activity,
        )

    return await _recalculate_and_refresh(
        room_id,
        queue_entry_id,
        "vote_updated",
        session=session,
        last_activity=await build_last_activity(
            "replay_vote", user_id, session, queue_entry_id=queue_entry_id
        ),
    )


async def _recalculate_and_refresh(
    room_id: str,
    queue_entry_id: str,
    event_type: str,
    session: AsyncSession | None = None,
    last_activity: dict[str, object] | None = None,
) -> dict[str, object]:
    """Helper to recalculate vote scores and return the fresh room state."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await _recalculate_and_refresh(
                room_id, queue_entry_id, event_type, session=new_session
            )
            await new_session.commit()
            return result

    queue_entry = await queue_entry_repo.get_queue_entry(
        queue_entry_id, session=session
    )
    if not queue_entry:
        return await refresh_room_state(
            room_id,
            event_type,
            session=session,
            last_activity=last_activity,
        )

    feedback_list = await song_feedback_repo.get_song_feedback_by_queue_entry(
        queue_entry_id, session=session
    )
    upvotes = sum(1 for feedback in feedback_list if feedback.type == FeedbackType.LIKE)
    downvotes = sum(
        1 for feedback in feedback_list if feedback.type == FeedbackType.DISLIKE
    )

    vote_score = upvotes - downvotes
    order_rank = float(queue_entry.position) - float(vote_score) / 100.0

    await queue_entry_repo.update_queue_entry(
        queue_entry_id,
        {
            "voteScore": vote_score,
            "orderRank": order_rank,
        },
        session=session,
    )

    return await refresh_room_state(
        room_id,
        event_type,
        session=session,
        last_activity=last_activity,
    )
