import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.playback_session_repo as playback_session_repo
import repositories.queue_entry_repo as queue_entry_repo
import repositories.room_repo as room_repo
import repositories.song_feedback_repo as song_feedback_repo
import repositories.track_repo as track_repo
import repositories.user_repo as user_repo
from core import identifiers
from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import (
    FeedbackType,
    PlaybackState,
    QueueEntryStatus,
    RoomStatus,
)
from services.playback_service import advance_to_next
from services.room_state_service import build_last_activity, refresh_room_state
from services.vote_service import vote_queue_entry


async def add_to_queue(
    room_id: str,
    track_data: dict[str, object],
    user_id: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await add_to_queue(
                room_id, track_data, user_id, session=new_session
            )
            await new_session.commit()
            return result

    if not track_data:
        raise HTTPException(status_code=400, detail="No track data provided")

    # Get room and validate
    try:
        room = await room_repo.get_room(room_id, session=session)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    # Get user
    try:
        await user_repo.get_user(user_id, session=session)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")

    # Get or create track
    db_track = await track_repo.get_track(str(track_data["trackId"]), session=session)
    if not db_track:
        db_track = await track_repo.create_track(
            {
                "trackId": track_data["trackId"],
                "providerTrackId": track_data["providerTrackId"],
                "title": track_data["title"],
                "artist": track_data["artist"],
                "album": track_data["album"],
                "duration": track_data["duration"],
                "coverUrl": track_data["coverUrl"],
                "deepLink": track_data["deepLink"],
            },
            session=session,
        )

    # Block duplicates only while an existing entry is still active (QUEUED/PLAYING).
    # Status filtering (excludes PLAYED, REMOVED, SKIPPED) is handled by get_queue_entry_by_track.
    existing_entry = await queue_entry_repo.get_queue_entry_by_track(
        room_id, str(track_data["trackId"]), session=session
    )
    if existing_entry:
        raise HTTPException(status_code=409, detail="Song is already in the queue")

    # Get max position and check for playing entries
    max_position = await queue_entry_repo.get_max_queue_position(
        room_id, session=session
    )
    next_position = max_position + 1
    has_playing = await queue_entry_repo.get_playing_queue_entry(
        room_id, session=session
    )

    # Create queue entry
    queue_entry_id = identifiers.generate_queue_entry_id()
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room_id,
            "trackId": track_data["trackId"],
            "addedBy": user_id,
            "position": next_position,
            "status": QueueEntryStatus.PLAYING
            if has_playing is None
            else QueueEntryStatus.QUEUED,
            "voteScore": 0,
            "orderRank": float(next_position),
        },
        session=session,
    )

    # Create playback session if this is the first entry (paused, host must resume)
    if has_playing is None:
        await playback_session_repo.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": queue_entry_id,
                "state": PlaybackState.PAUSED,
                "elapsedTime": 0,
            },
            session=session,
        )

    activity = await build_last_activity(
        "track_added", user_id, session, queue_entry_id=queue_entry_id
    )
    return await refresh_room_state(
        room_id, "queue_updated", session=session, last_activity=activity
    )


async def remove_queue_entry(
    room_id: str,
    queue_entry_id: str,
    user_id: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await remove_queue_entry(
                room_id, queue_entry_id, user_id, session=new_session
            )
            await new_session.commit()
            return result

    queue_entry = await queue_entry_repo.get_queue_entry(
        queue_entry_id, session=session
    )
    if not queue_entry or queue_entry.roomId != room_id:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    try:
        room = await room_repo.get_room(room_id, session=session)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    is_adder = queue_entry.addedBy == user_id
    is_host = room.hostedBy == user_id

    if is_host:
        can_remove_directly = True
    elif is_adder:
        feedback_list = await song_feedback_repo.get_song_feedback_by_queue_entry(
            queue_entry_id, session=session
        )
        has_upvotes = any(f.type == FeedbackType.LIKE for f in feedback_list)
        can_remove_directly = not has_upvotes
    else:
        can_remove_directly = False

    if not can_remove_directly:
        # Democratic vote path
        return await vote_queue_entry(
            room_id, queue_entry_id, user_id, "skip", session=session
        )

    if queue_entry.status == QueueEntryStatus.PLAYING:
        await advance_to_next(room_id, session=session)
        await queue_entry_repo.update_queue_entry(
            queue_entry_id, {"status": QueueEntryStatus.REMOVED}, session=session
        )
    else:
        await queue_entry_repo.update_queue_entry(
            queue_entry_id, {"status": QueueEntryStatus.REMOVED}, session=session
        )

    activity = await build_last_activity(
        "track_removed", user_id, session, queue_entry_id=queue_entry_id
    )
    return await refresh_room_state(
        room_id, "queue_updated", session=session, last_activity=activity
    )
