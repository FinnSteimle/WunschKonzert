import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.playback_history_repo as playback_history_repo
import repositories.playback_session_repo as playback_session_repo
import repositories.queue_entry_repo as queue_entry_repo
import repositories.room_repo as room_repo
import repositories.song_feedback_repo as song_feedback_repo
from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import (
    FeedbackType,
    PlaybackSession,
    PlaybackState,
    QueueEntryStatus,
)
from services.room_state_service import (
    build_last_activity,
    refresh_room_state,
    room_state_cache,
)


async def sync_playback_position(
    room_id: str,
    user_id: str,
    position_ms: int,
    queue_entry_id: str | None = None,
    session: AsyncSession | None = None,
) -> None:
    """Lightweight position sync: update DB + patch cache without full rebuild."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            await sync_playback_position(
                room_id, user_id, position_ms, queue_entry_id, session=new_session
            )
            await new_session.commit()
            return

    try:
        room = await room_repo.get_room(room_id, session=session)
    except ResourceNotFoundError:
        return

    if room.hostedBy != user_id:
        return

    playback_session = await playback_session_repo.get_current_playback_session(
        room_id, session=session
    )
    if not playback_session or str(playback_session.state.value) != "playing":
        return

    # If a queue_entry_id is provided, ensure it matches the current session
    if queue_entry_id and playback_session.queueEntryId != queue_entry_id:
        return

    elapsed = max(0, position_ms // 1000)
    await playback_session_repo.update_playback_session(
        playback_session.playbackSessionId, {"elapsedTime": elapsed}, session=session
    )

    cached = room_state_cache.get(room_id)
    if cached:
        playback = cached.get("playback")
        if isinstance(playback, dict):
            playback["positionMs"] = elapsed * 1000


async def set_playback_state(
    room_id: str,
    user_id: str,
    action: str,
    position_ms: int | None = None,
    queue_entry_id: str | None = None,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await set_playback_state(
                room_id,
                user_id,
                action,
                position_ms,
                queue_entry_id,
                session=new_session,
            )
            await new_session.commit()
            return result

    if action not in {"pause", "resume", "stop", "advance"}:
        raise HTTPException(status_code=400, detail="Invalid playback action")

    try:
        room = await room_repo.get_room(room_id, session=session)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.hostedBy != user_id:
        raise HTTPException(
            status_code=403, detail="Only the host can control playback"
        )

    if action == "advance":
        return await advance_to_next(room_id, user_id, session=session)

    playback_session = await playback_session_repo.get_current_playback_session(
        room_id, session=session
    )

    if not playback_session:
        playback_session = await _initialize_playback_session(room_id, session=session)

    # Convince mypy that playback_session is not None
    if not playback_session:
        raise HTTPException(
            status_code=500, detail="Failed to initialize playback session"
        )

    elapsed_seconds = (
        max(0, int(position_ms) // 1000) if position_ms is not None else None
    )

    # If resuming and a queue_entry_id is provided, ignore position if it's for a different track.
    if (
        action == "resume"
        and queue_entry_id
        and playback_session.queueEntryId != queue_entry_id
    ):
        elapsed_seconds = None

    updates = _determine_playback_updates(action, elapsed_seconds)

    await playback_session_repo.update_playback_session(
        playback_session.playbackSessionId, updates, session=session
    )

    activity_type = {
        "pause": "playback_paused",
        "resume": "playback_resumed",
        "stop": "playback_stopped",
    }[action]
    activity = await build_last_activity(
        activity_type,
        user_id,
        session,
        queue_entry_id=playback_session.queueEntryId,
    )

    return await refresh_room_state(
        room_id,
        "playback_updated",
        session=session,
        last_activity=activity,
    )


async def _initialize_playback_session(
    room_id: str, session: AsyncSession | None = None
) -> PlaybackSession:
    """Initialize a new playback session if none exists."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await _initialize_playback_session(room_id, session=new_session)
            await new_session.commit()
            return result

    current_queue_entry = await queue_entry_repo.get_first_queued_entry(
        room_id, session=session
    )

    if not current_queue_entry:
        raise HTTPException(status_code=400, detail="No queued songs")

    await queue_entry_repo.update_queue_entry(
        current_queue_entry.queueEntryId,
        {"status": QueueEntryStatus.PLAYING},
        session=session,
    )

    return await playback_session_repo.create_playback_session(
        {
            "playbackSessionId": str(uuid.uuid4()),
            "roomId": room_id,
            "queueEntryId": current_queue_entry.queueEntryId,
            "state": PlaybackState.PLAYING,
            "elapsedTime": 0,
        },
        session=session,
    )


def _determine_playback_updates(
    action: str, elapsed_seconds: int | None
) -> dict[str, object]:
    """Determine the updates for a playback session based on the action."""
    now = datetime.now(UTC).replace(tzinfo=None)
    updates: dict[str, object] = {"state": PlaybackState.PLAYING, "pausedAt": None}

    if action == "pause":
        updates = {"state": PlaybackState.PAUSED, "pausedAt": now}
    elif action == "stop":
        updates = {"state": PlaybackState.STOPPED, "pausedAt": now}

    if elapsed_seconds is not None:
        updates["elapsedTime"] = elapsed_seconds

    return updates


async def advance_to_next(
    room_id: str,
    user_id: str | None = None,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    """Mark the current song as played and start the next highest-voted song."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await advance_to_next(room_id, user_id, session=new_session)
            await new_session.commit()
            return result

    current_session = await playback_session_repo.get_current_playback_session(
        room_id, session=session
    )
    if current_session:
        await playback_session_repo.update_playback_session(
            current_session.playbackSessionId,
            {
                "state": PlaybackState.STOPPED,
                "pausedAt": datetime.now(UTC).replace(tzinfo=None),
            },
            session=session,
        )
        await queue_entry_repo.update_queue_entry(
            current_session.queueEntryId,
            {"status": QueueEntryStatus.PLAYED},
            session=session,
        )

        await playback_history_repo.add_history_entry(
            {
                "roomId": room_id,
                "queueEntryId": current_session.queueEntryId,
                "playedAt": current_session.startedAt,
                "replayCount": 1,
            },
            session=session,
        )

    next_entry = await queue_entry_repo.get_next_queued_entry(room_id, session=session)
    if next_entry:
        await queue_entry_repo.update_queue_entry(
            next_entry.queueEntryId,
            {"status": QueueEntryStatus.PLAYING},
            session=session,
        )
        # Playback deadline: once the song reaches the playback all votes to skip it will be removed and the song will play.
        await song_feedback_repo.delete_song_feedback(
            next_entry.queueEntryId, feedback_type=FeedbackType.SKIP, session=session
        )

        await playback_session_repo.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": next_entry.queueEntryId,
                "state": PlaybackState.PLAYING,
                "elapsedTime": 0,
            },
            session=session,
        )

    activity = None
    if current_session and user_id:
        activity = await build_last_activity(
            "playback_advanced",
            user_id,
            session,
            queue_entry_id=current_session.queueEntryId,
        )
    return await refresh_room_state(
        room_id,
        "playback_updated",
        session=session,
        last_activity=activity,
    )
