import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

import repositories.crud as crud
from core.exceptions import ResourceNotFoundError
from models.domain import (
    FeedbackType,
    MembershipStatus,
    PlaybackState,
    QueueEntryStatus,
    RoomStatus,
)

# Shared state moved to service (or could be in core if needed by multiple services)
room_state_cache: dict[str, dict] = {}

# Join code validation pattern
JOIN_CODE_RE = re.compile(r"^[A-HJ-NP-Z2-9]{6}$")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _enum_value(value: object) -> str:
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _feedback_to_ui(feedback_type: FeedbackType) -> str:
    return "upvote" if feedback_type == FeedbackType.LIKE else "downvote"


def _ui_to_feedback(vote_type: str) -> FeedbackType | None:
    if vote_type == "upvote":
        return FeedbackType.LIKE
    if vote_type == "downvote":
        return FeedbackType.DISLIKE
    return None


async def _build_room_state(room_id: str) -> dict | None:
    # Get room and host
    room = await crud.get_room(room_id)
    if not room:
        return None

    host = await crud.get_user(room.hostedBy)
    if not host:
        return None

    # Get room members
    memberships = await crud.get_room_members(room_id)

    users: list[dict] = [
        {
            "user": {
                "userId": host.userId,
                "displayName": host.displayName,
                "createdAt": host.createdAt.isoformat(),
            },
            "membership": {
                "joinedAt": room.createdAt.isoformat(),
                "leftAt": None,
                "membershipStatus": "active",
            },
        }
    ]
    seen_user_ids = {host.userId}
    for membership, user in memberships:
        if user.userId in seen_user_ids:
            continue
        seen_user_ids.add(user.userId)
        users.append(
            {
                "user": {
                    "userId": user.userId,
                    "displayName": user.displayName,
                    "createdAt": user.createdAt.isoformat(),
                },
                "membership": {
                    "joinedAt": membership.joinedAt.isoformat(),
                    "leftAt": membership.leftAt.isoformat()
                    if membership.leftAt
                    else None,
                    "membershipStatus": _enum_value(membership.membershipStatus),
                },
            }
        )

    # Get queue entries with tracks and users
    queue_entries = await crud.get_queue_entries(room_id)
    queue_entry_ids = [entry.queueEntryId for entry in queue_entries]

    # Build feedback map
    feedback_map = {entry_id: [] for entry_id in queue_entry_ids}

    for entry_id in queue_entry_ids:
        feedback_list = await crud.get_song_feedback_by_queue_entry(entry_id)
        feedback_map[entry_id].extend(feedback_list)

    # Build queue
    queue: list[dict] = []
    for queue_entry in queue_entries:
        track = await crud.get_track(queue_entry.trackId)
        added_by_user = await crud.get_user(queue_entry.addedBy)

        if not track or not added_by_user:
            continue

        feedback_entries = feedback_map.get(queue_entry.queueEntryId, [])
        upvotes = sum(
            1 for feedback in feedback_entries if feedback.type == FeedbackType.LIKE
        )
        downvotes = sum(
            1 for feedback in feedback_entries if feedback.type == FeedbackType.DISLIKE
        )
        vote_score = upvotes - downvotes

        queue.append(
            {
                "queueEntryId": queue_entry.queueEntryId,
                "track": {
                    "trackId": track.trackId,
                    "providerTrackId": track.providerTrackId,
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album or "",
                    "duration": track.duration or 0,
                    "coverUrl": track.coverUrl or "",
                    "deepLink": track.deepLink or "",
                },
                "addedBy": {
                    "userId": added_by_user.userId,
                    "displayName": added_by_user.displayName,
                },
                "queuedAt": queue_entry.queuedAt.isoformat(),
                "position": queue_entry.position,
                "status": _enum_value(queue_entry.status),
                "voteScore": vote_score,
                "orderRank": float(queue_entry.orderRank or queue_entry.position),
                "feedback": [
                    {
                        "userId": feedback.userId,
                        "votedAt": feedback.votedAt.isoformat(),
                        "type": _feedback_to_ui(feedback.type),
                    }
                    for feedback in feedback_entries
                ],
            }
        )

    queue.sort(
        key=lambda item: (
            0 if item["status"] == "playing" else 1,
            -item["voteScore"],
            item["position"],
        )
    )

    # Get latest playback session
    latest_playback = await crud.get_current_playback_session(room_id)

    playback = {
        "state": "stopped",
        "currentQueueEntryId": None,
        "updatedAt": _now_iso(),
        "positionMs": 0,
    }
    if latest_playback:
        playback_state = _enum_value(latest_playback.state)
        playback = {
            "state": playback_state,
            "currentQueueEntryId": (
                latest_playback.queueEntryId if playback_state != "stopped" else None
            ),
            "updatedAt": latest_playback.startedAt.isoformat(),
            "positionMs": int(latest_playback.elapsedTime or 0) * 1000,
        }

    state = {
        "room": {
            "roomId": room.roomId,
            "joinCode": room.joinCode,
            "name": room.name,
            "status": _enum_value(room.status),
            "createdAt": room.createdAt.isoformat(),
            "supportedProviderId": room.supportedProviderId,
        },
        "host": {
            "userId": host.userId,
            "displayName": host.displayName,
            "createdAt": host.createdAt.isoformat(),
        },
        "users": users,
        "queue": queue,
        "playback": playback,
    }

    return state


async def refresh_room_state(room_id: str, event_type: str | None = None) -> dict:
    room_state = await _build_room_state(room_id)
    if room_state is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if event_type:
        room_state["lastEvent"] = {"type": event_type, "at": _now_iso()}

    room_state_cache[room_id] = room_state
    return room_state


async def add_to_queue(room_id: str, track_data: dict, user_id: str) -> dict:
    if not track_data:
        raise HTTPException(status_code=400, detail="No track data provided")

    # Get room and validate
    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    # Get user
    user = await crud.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get or create track
    db_track = await crud.get_track(track_data["trackId"])
    if not db_track:
        db_track = await crud.create_track(
            {
                "trackId": track_data["trackId"],
                "providerTrackId": track_data["providerTrackId"],
                "title": track_data["title"],
                "artist": track_data["artist"],
                "album": track_data["album"],
                "duration": track_data["duration"],
                "coverUrl": track_data["coverUrl"],
                "deepLink": track_data["deepLink"],
            }
        )

    # Check if the song is already in the queue
    existing_entry = await crud.get_queue_entry_by_track(room_id, track_data["trackId"])
    if existing_entry:
        raise HTTPException(status_code=409, detail="Song is already in the queue")

    # Get max position and check for playing entries
    max_position = await crud.get_max_queue_position(room_id)
    next_position = max_position + 1
    has_playing = await crud.get_playing_queue_entry(room_id)

    # Create queue entry
    queue_entry_id = f"QENTRY{uuid.uuid4().hex[:8].upper()}"
    await crud.create_queue_entry(
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
        }
    )

    # Create playback session if this is the first entry
    if has_playing is None:
        await crud.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": queue_entry_id,
                "state": PlaybackState.PLAYING,
                "elapsedTime": 0,
            }
        )

    return await refresh_room_state(room_id, "queue_updated")


async def vote_queue_entry(
    room_id: str, queue_entry_id: str, user_id: str, vote_type: str
) -> dict:
    if vote_type not in {"upvote", "downvote", "neutral"}:
        raise HTTPException(status_code=400, detail="Invalid vote type")

    # Get queue entry
    queue_entry = await crud.get_queue_entry(queue_entry_id)
    if not queue_entry or queue_entry.roomId != room_id:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    if vote_type == "neutral":
        await crud.delete_song_feedback(queue_entry_id, user_id)
    else:
        mapped_feedback = _ui_to_feedback(vote_type)
        if mapped_feedback is None:
            raise HTTPException(status_code=400, detail="Invalid vote type")

        await crud.create_or_update_song_feedback(
            {
                "queueEntryId": queue_entry_id,
                "userId": user_id,
                "type": mapped_feedback,
                "votedAt": datetime.now(UTC).replace(tzinfo=None),
            }
        )

    # Recalculate vote score
    feedback_list = await crud.get_song_feedback_by_queue_entry(queue_entry_id)
    upvotes = sum(1 for feedback in feedback_list if feedback.type == FeedbackType.LIKE)
    downvotes = sum(
        1 for feedback in feedback_list if feedback.type == FeedbackType.DISLIKE
    )

    vote_score = upvotes - downvotes
    order_rank = float(queue_entry.position) - float(vote_score) / 100.0

    # Update queue entry
    await crud.update_queue_entry(
        queue_entry_id,
        {
            "voteScore": vote_score,
            "orderRank": order_rank,
        },
    )

    return await refresh_room_state(room_id, "vote_updated")


async def set_playback_state(room_id: str, user_id: str, action: str) -> dict:
    if action not in {"pause", "resume", "stop"}:
        raise HTTPException(status_code=400, detail="Invalid playback action")

    # Get room and validate
    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.hostedBy != user_id:
        raise HTTPException(
            status_code=403, detail="Only the host can control playback"
        )

    # Get or create playback session
    playback_session = await crud.get_current_playback_session(room_id)

    if not playback_session:
        # Get first queued entry
        current_queue_entry = await crud.get_first_queued_entry(room_id)

        if not current_queue_entry:
            raise HTTPException(status_code=400, detail="No queued songs")

        # Update queue entry status
        await crud.update_queue_entry(
            current_queue_entry.queueEntryId, {"status": QueueEntryStatus.PLAYING}
        )

        # Create playback session
        playback_session = await crud.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": current_queue_entry.queueEntryId,
                "state": PlaybackState.PLAYING,
                "elapsedTime": 0,
            }
        )

    # Update playback session state
    updates = {"state": PlaybackState.PLAYING, "pausedAt": None}
    if action == "pause":
        updates = {
            "state": PlaybackState.PAUSED,
            "pausedAt": datetime.now(UTC).replace(tzinfo=None),
        }
    elif action == "stop":
        updates = {
            "state": PlaybackState.STOPPED,
            "pausedAt": datetime.now(UTC).replace(tzinfo=None),
        }

    await crud.update_playback_session(playback_session.playbackSessionId, updates)

    return await refresh_room_state(room_id, "playback_updated")


async def leave_room_service(room_id: str, user_id: str) -> dict:
    user = await crud.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.hostedBy == user_id:
        raise HTTPException(
            status_code=403,
            detail="Hosts cannot leave the room. Please delete the room instead.",
        )

    await crud.leave_room(user_id, room_id)
    return await refresh_room_state(room_id, "participant_left")


async def delete_room_service(room_id: str, user_id: str) -> dict:
    # Get room and validate
    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.hostedBy != user_id:
        raise HTTPException(status_code=403, detail="Only host can delete room")

    # Update room status
    await crud.update_room_status(room_id, RoomStatus.DELETED)

    # Update all memberships
    memberships = await crud.get_room_memberships(room_id)
    from core.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        for membership in memberships:
            # Re-fetch or merge into session if needed, but here we can just update
            membership = await session.merge(membership)
            membership.membershipStatus = MembershipStatus.INACTIVE
            if membership.leftAt is None:
                membership.leftAt = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

    return await refresh_room_state(room_id, "room_deleted")


async def ensure_user_display_name(user_id: str, display_name: str) -> None:
    trimmed = display_name.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Display name is required")
    if len(trimmed) > 60:
        raise HTTPException(status_code=400, detail="Display name is too long")

    user_exists = True
    try:
        await crud.get_user(user_id)
    except ResourceNotFoundError:
        user_exists = False

    if not user_exists:
        try:
            await crud.create_user(user_id, trimmed)
            return
        except ValueError as e:
            if "already exists" not in str(e):
                raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        await crud.update_user_display_name(user_id, trimmed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


async def ensure_provider_exists(provider_id: str) -> None:
    from core.exceptions import ResourceNotFoundError

    try:
        await crud.get_music_provider(provider_id)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported music provider: {provider_id}. "
        )


async def ensure_active_membership(user_id: str, room_id: str) -> None:
    try:
        await crud.update_membership_status(user_id, room_id, MembershipStatus.ACTIVE)
    except ValueError:
        # Membership doesn't exist, create it
        await crud.create_room_membership(user_id, room_id)


async def rename_participant(room_id: str, user_id: str, display_name: str) -> dict:
    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    membership = await crud.get_room_membership(user_id, room_id)
    if not membership or membership.membershipStatus != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=403, detail="Only active room participants can rename"
        )

    await ensure_user_display_name(user_id, display_name)
    return await refresh_room_state(room_id, "participant_renamed")


async def check_room_availability(
    join_codes: list[str],
) -> tuple[list[str], list[str]]:
    """
    Check availability of rooms by join codes.

    Returns a tuple of (available_codes, unavailable_codes).
    Unavailable codes include invalid, duplicate, and non-existent/inactive rooms.
    """
    unique_codes: list[str] = []
    seen_codes: set[str] = set()
    invalid_or_duplicate_codes: list[str] = []

    for raw_code in join_codes:
        normalized_code = raw_code.strip().upper()
        if not JOIN_CODE_RE.match(normalized_code):
            invalid_or_duplicate_codes.append(normalized_code)
            continue
        if normalized_code in seen_codes:
            invalid_or_duplicate_codes.append(normalized_code)
            continue
        seen_codes.add(normalized_code)
        unique_codes.append(normalized_code)

    available = await crud.get_active_join_codes(unique_codes)
    available_set = set(available)
    unavailable = [
        code for code in unique_codes if code not in available_set
    ] + invalid_or_duplicate_codes

    return available, unavailable
