import re
from datetime import UTC, datetime
from typing import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.playback_history_repo as playback_history_repo
import repositories.room_repo as room_repo
import repositories.user_repo as user_repo
from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import (
    Account,
    FeedbackType,
    MembershipStatus,
    PlaybackHistoryEntry,
    Room,
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
    if feedback_type == FeedbackType.LIKE:
        return "upvote"
    if feedback_type == FeedbackType.DISLIKE:
        return "downvote"
    if feedback_type == FeedbackType.SKIP:
        return "skip"
    if feedback_type == FeedbackType.REPLAY:
        return "replay"
    raise RuntimeError("Feedback type not recognized.")


def ui_to_feedback(vote_type: str) -> FeedbackType | None:
    if vote_type == "upvote":
        return FeedbackType.LIKE
    if vote_type == "downvote":
        return FeedbackType.DISLIKE
    if vote_type == "skip":
        return FeedbackType.SKIP
    if vote_type == "replay":
        return FeedbackType.REPLAY
    return None


def _build_user_list(room: Room) -> list[dict[str, object]]:
    host = room.host
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
    for membership in room.memberships:
        user = membership.user
        if (
            user.userId in seen_user_ids
            or membership.membershipStatus != MembershipStatus.ACTIVE
        ):
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
    return users


def _build_queue_list(room: Room) -> list[dict[str, object]]:
    queue: list[dict[str, object]] = []
    for queue_entry in room.queue_entries:
        track = queue_entry.track
        added_by_user = queue_entry.added_by

        if not track or not added_by_user:
            continue

        feedback_entries = queue_entry.song_feedback
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
    return queue


def _build_playback_state(room: Room) -> dict[str, object]:
    latest_playback = None
    if room.playback_sessions:
        latest_playback = sorted(
            room.playback_sessions, key=lambda s: s.startedAt, reverse=True
        )[0]

    playback: dict[str, object] = {
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
            "positionMs": (
                int(latest_playback.elapsedTime or 0) * 1000
                if playback_state != "stopped"
                else 0
            ),
        }
    return playback


def _build_history_list(
    history_entries: Sequence[PlaybackHistoryEntry],
) -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    for entry in history_entries:
        if not entry.queue_entry or not entry.queue_entry.track:
            continue
        track = entry.queue_entry.track
        history.append(
            {
                "historyId": entry.id,
                "playedAt": entry.playedAt.isoformat(),
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
            }
        )
    return history


async def _build_room_state(
    room_id: str, session: AsyncSession | None = None
) -> dict[str, object] | None:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await _build_room_state(room_id, session=new_session)

    try:
        room = await room_repo.get_room_with_full_state(room_id, session=session)
        host = room.host
    except ResourceNotFoundError:
        return None

    users = _build_user_list(room)
    queue = _build_queue_list(room)
    playback = _build_playback_state(room)

    history_entries = await playback_history_repo.get_history(
        room_id, limit=20, session=session
    )
    history = _build_history_list(history_entries)

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
        "history": history,
    }

    _preserve_ephemeral_fields(room_id, state)
    return state


def _preserve_ephemeral_fields(room_id: str, state: dict[str, object]) -> None:
    """Carry in-memory-only fields across rebuilds."""
    previous = room_state_cache.get(room_id)
    if not isinstance(previous, dict):
        return
    last_activity = previous.get("lastActivity")
    if isinstance(last_activity, dict):
        state["lastActivity"] = last_activity
    transfer = previous.get("transfer")
    if isinstance(transfer, dict):
        state["transfer"] = transfer
    messages = previous.get("systemMessages")
    if isinstance(messages, list):
        state["systemMessages"] = messages


async def build_last_activity(
    activity_type: str,
    user_id: str,
    session: AsyncSession | None = None,
    queue_entry_id: str | None = None,
) -> dict[str, object]:
    """Build a user-facing activity payload for the room state cache."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await build_last_activity(
                activity_type,
                user_id,
                session=new_session,
                queue_entry_id=queue_entry_id,
            )

    user = await user_repo.get_user(user_id, session=session)
    username = user.displayName

    # Prefer the stored account username when available, but keep the visible
    # display name as a safe fallback for rooms without a linked account.
    account_username = None
    result = await session.execute(
        select(Account.username).where(Account.userId == user_id)
    )
    account_username = result.scalar_one_or_none()
    if account_username:
        username = account_username

    activity: dict[str, object] = {
        "type": activity_type,
        "userId": user_id,
        "username": username,
        "at": _now_iso(),
    }
    if queue_entry_id:
        activity["queueEntryId"] = queue_entry_id
    return activity


async def refresh_room_state(
    room_id: str,
    event_type: str | None = None,
    session: AsyncSession | None = None,
    last_activity: dict[str, object] | None = None,
) -> dict[str, object]:
    room_state = await _build_room_state(room_id, session=session)
    if room_state is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if event_type:
        room_state["lastEvent"] = {"type": event_type, "at": _now_iso()}
    if last_activity is not None:
        room_state["lastActivity"] = last_activity

    room_state_cache[room_id] = room_state
    return room_state


async def get_song_history(room_id: str) -> dict[str, object]:
    return await refresh_room_state(room_id, "history_updated")
