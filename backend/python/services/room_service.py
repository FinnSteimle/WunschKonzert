import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

import repositories.crud as crud
import repositories.membership_repo as membership_repo
import repositories.room_repo as room_repo
from core.exceptions import ResourceNotFoundError
from models.domain import (
    FeedbackType,
    MembershipStatus,
    PlaybackState,
    QueueEntryStatus,
    RoomStatus,
    SongFeedback,
)

# Shared state moved to service (or could be in core if needed by multiple services)
room_state_cache: dict[str, dict[str, object]] = {}

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


async def _build_room_state(room_id: str) -> dict[str, object] | None:
    # Get room and host
    try:
        room = await room_repo.get_room(room_id)
        host = await crud.get_user(room.hostedBy)
    except ResourceNotFoundError:
        return None

    # Get room members
    memberships_list = await membership_repo.get_room_active_memberships(room_id)

    users: list[dict[str, object]] = [
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
    for membership, user in memberships_list:
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
    feedback_map: dict[str, list[SongFeedback]] = {
        entry_id: [] for entry_id in queue_entry_ids
    }

    for entry_id in queue_entry_ids:
        feedback_list = await crud.get_song_feedback_by_queue_entry(entry_id)
        feedback_map[entry_id].extend(feedback_list)

    # Build queue
    queue: list[dict[str, object]] = []
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
            -int(item["voteScore"]),  # type: ignore[call-overload]
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

    state: dict[str, object] = {
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


async def refresh_room_state(
    room_id: str, event_type: str | None = None
) -> dict[str, object]:
    room_state = await _build_room_state(room_id)
    if room_state is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if event_type:
        room_state["lastEvent"] = {"type": event_type, "at": _now_iso()}

    room_state_cache[room_id] = room_state
    return room_state


async def sync_playback_position(room_id: str, user_id: str, position_ms: int) -> None:
    """Lightweight position sync: update DB + patch cache without full rebuild."""
    try:
        room = await room_repo.get_room(room_id)
    except ResourceNotFoundError:
        return

    if room.hostedBy != user_id:
        return

    session = await crud.get_current_playback_session(room_id)
    if not session or _enum_value(session.state) != "playing":
        return

    elapsed = max(0, position_ms // 1000)
    await crud.update_playback_session(
        session.playbackSessionId, {"elapsedTime": elapsed}
    )

    cached = room_state_cache.get(room_id)
    if cached:
        playback = cached.get("playback")
        if isinstance(playback, dict):
            playback["positionMs"] = elapsed * 1000


async def add_to_queue(
    room_id: str, track_data: dict[str, object], user_id: str
) -> dict[str, object]:
    if not track_data:
        raise HTTPException(status_code=400, detail="No track data provided")

    # Get room and validate
    try:
        room = await room_repo.get_room(room_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    # Get user
    try:
        await crud.get_user(user_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")

    # Get or create track
    db_track = await crud.get_track(str(track_data["trackId"]))
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
    existing_entry = await crud.get_queue_entry_by_track(
        room_id, str(track_data["trackId"])
    )
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
) -> dict[str, object]:
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


async def set_playback_state(
    room_id: str,
    user_id: str,
    action: str,
    position_ms: int | None = None,
) -> dict[str, object]:
    if action not in {"pause", "resume", "stop", "advance"}:
        raise HTTPException(status_code=400, detail="Invalid playback action")

    try:
        room = await room_repo.get_room(room_id)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.hostedBy != user_id:
        raise HTTPException(
            status_code=403, detail="Only the host can control playback"
        )

    if action == "advance":
        return await _advance_to_next(room_id)

    playback_session = await crud.get_current_playback_session(room_id)

    if not playback_session:
        current_queue_entry = await crud.get_first_queued_entry(room_id)

        if not current_queue_entry:
            raise HTTPException(status_code=400, detail="No queued songs")

        await crud.update_queue_entry(
            current_queue_entry.queueEntryId, {"status": QueueEntryStatus.PLAYING}
        )

        playback_session = await crud.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": current_queue_entry.queueEntryId,
                "state": PlaybackState.PLAYING,
                "elapsedTime": 0,
            }
        )

    elapsed_seconds = (
        max(0, int(position_ms) // 1000) if position_ms is not None else None
    )

    updates: dict[str, object] = {"state": PlaybackState.PLAYING, "pausedAt": None}
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

    if elapsed_seconds is not None:
        updates["elapsedTime"] = elapsed_seconds

    await crud.update_playback_session(playback_session.playbackSessionId, updates)

    return await refresh_room_state(room_id, "playback_updated")


async def _advance_to_next(room_id: str) -> dict[str, object]:
    """Mark the current song as played and start the next highest-voted song."""
    current_session = await crud.get_current_playback_session(room_id)
    if current_session:
        await crud.update_playback_session(
            current_session.playbackSessionId,
            {
                "state": PlaybackState.STOPPED,
                "pausedAt": datetime.now(UTC).replace(tzinfo=None),
            },
        )
        await crud.update_queue_entry(
            current_session.queueEntryId, {"status": QueueEntryStatus.PLAYED}
        )

    next_entry = await crud.get_next_queued_entry(room_id)
    if next_entry:
        await crud.update_queue_entry(
            next_entry.queueEntryId, {"status": QueueEntryStatus.PLAYING}
        )
        await crud.create_playback_session(
            {
                "playbackSessionId": str(uuid.uuid4()),
                "roomId": room_id,
                "queueEntryId": next_entry.queueEntryId,
                "state": PlaybackState.PLAYING,
                "elapsedTime": 0,
            }
        )

    return await refresh_room_state(room_id, "playback_advanced")


async def leave_room_service(room_id: str, user_id: str) -> dict[str, object]:
    try:
        try:
            await crud.get_user(user_id)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            room = await room_repo.get_room(room_id)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.hostedBy == user_id:
            raise HTTPException(
                status_code=403,
                detail="Hosts cannot leave the room. Please delete the room instead.",
            )

        await membership_repo.leave_room(user_id, room_id)
        return await refresh_room_state(room_id, "participant_left")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


async def create_room_service(
    name: str, user_id: str, display_name: str, supported_provider_id: str
) -> dict[str, object]:
    """Create a new room, validating user and provider."""
    await ensure_user_display_name(user_id, display_name)
    await ensure_provider_exists(supported_provider_id)

    pa = await crud.get_provider_account_by_user(user_id, supported_provider_id)
    if not pa or not pa.refreshToken:
        raise HTTPException(
            status_code=403,
            detail="You must link your Spotify account before creating a room",
        )

    try:
        room = await room_repo.create_room(
            user_id,
            supported_provider_id,
            name,
        )
        await ensure_active_membership(user_id, room.roomId)
        await refresh_room_state(room.roomId, "room_created")
        return {
            "success": True,
            "message": f"Successfully created room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=400, detail="Room already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Re-raise HTTPExceptions, wrap others in 500
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


async def join_room_service(
    join_code: str, user_id: str, display_name: str
) -> dict[str, object]:
    """Validate and join a room by its join code."""
    if display_name is None or not display_name.strip():
        raise HTTPException(status_code=400, detail="Display name is required")

    normalized_code = join_code.strip().upper()
    if not JOIN_CODE_RE.match(normalized_code):
        raise HTTPException(
            status_code=422,
            detail="Join code must be exactly 6 characters (A-Z, 2-9, no I/O/0/1).",
        )

    await ensure_user_display_name(user_id, display_name)

    try:
        room = await room_repo.get_room_by_join_code(normalized_code)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(
            status_code=410,
            detail="This session has ended and is no longer available.",
        )

    try:
        await ensure_active_membership(user_id, room.roomId)
        await refresh_room_state(room.roomId, "participant_joined")
        return {
            "success": True,
            "message": f"Successfully joined room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to join room: {str(e)}")


async def delete_room_service(room_id: str, user_id: str) -> dict[str, object]:
    try:
        # Get room and validate
        room = await room_repo.get_room(room_id)
        if room.hostedBy != user_id:
            raise HTTPException(status_code=403, detail="Only host can delete room")

        # Update room status
        await room_repo.update_room_status(room_id, RoomStatus.DELETED)

        # Update all memberships
        memberships_list = await membership_repo.get_room_memberships(room_id)
        from core.database import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            for membership in memberships_list:
                # Re-fetch or merge into session if needed, but here we can just update
                membership = await session.merge(membership)
                membership.membershipStatus = MembershipStatus.INACTIVE
                if membership.leftAt is None:
                    membership.leftAt = datetime.now(UTC).replace(tzinfo=None)
            await session.commit()

        return await refresh_room_state(room_id, "room_deleted")
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to delete room: {str(e)}")


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
    except ResourceNotFoundError as e:
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
        await membership_repo.update_room_membership_status(
            user_id, room_id, MembershipStatus.ACTIVE
        )
    except ResourceNotFoundError:
        # Membership doesn't exist, create it
        await membership_repo.create_room_membership(user_id, room_id)


async def rename_participant(
    room_id: str, user_id: str, display_name: str
) -> dict[str, object]:
    try:
        try:
            await room_repo.get_room(room_id)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="Room not found")

        try:
            membership = await membership_repo.get_room_membership(user_id, room_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=403, detail="Only active room participants can rename"
            )

        if membership.membershipStatus != MembershipStatus.ACTIVE:
            raise HTTPException(
                status_code=403, detail="Only active room participants can rename"
            )

        await ensure_user_display_name(user_id, display_name)
        return await refresh_room_state(room_id, "participant_renamed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500, detail=f"Failed to rename participant: {str(e)}"
        )


async def check_room_availability(
    join_codes: list[str],
) -> tuple[list[str], list[str]]:
    """
    Check availability of rooms by join codes.

    Returns a tuple of (available_codes, unavailable_codes).
    Unavailable codes include invalid, duplicate, and non-existent/inactive room_repo.
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

    available = await room_repo.get_all_active_rooms_by_join_codes(unique_codes)
    available_set = set(available)
    unavailable = [
        code for code in unique_codes if code not in available_set
    ] + invalid_or_duplicate_codes

    return available, unavailable
