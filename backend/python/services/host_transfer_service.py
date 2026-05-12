from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

import repositories.membership_repo as membership_repo
import repositories.music_provider_repo as music_provider_repo
import repositories.queue_entry_repo as queue_entry_repo
import repositories.room_repo as room_repo
import repositories.track_repo as track_repo
import services.room_service as room_service
from core.exceptions import ResourceNotFoundError
from models.domain import MembershipStatus, QueueEntryStatus
from services.providers.registry import get_provider_client

MAX_SYSTEM_MESSAGES = 5


def _time_now() -> str:
    return datetime.now(UTC).isoformat()


def _get_transfer(room_id: str) -> dict[str, object] | None:
    cached = room_service.room_state_cache.get(room_id)
    if not cached:
        return None
    transfer = cached.get("transfer")
    return transfer if isinstance(transfer, dict) else None


def _set_transfer(room_id: str, transfer: dict[str, object] | None) -> None:
    cached = room_service.room_state_cache.get(room_id)
    if cached is None:
        return
    if transfer is None:
        cached.pop("transfer", None)
    else:
        cached["transfer"] = transfer


def _push_system_message(room_id: str, text: str) -> None:
    cached = room_service.room_state_cache.get(room_id)
    if cached is None:
        return
    messages = cached.get("systemMessages")
    if not isinstance(messages, list):
        messages = []
    messages.append({"id": str(uuid.uuid4()), "text": text, "at": _time_now()})
    cached["systemMessages"] = messages[-MAX_SYSTEM_MESSAGES:]


async def initiate_transfer(
    room_id: str, from_user_id: str, to_user_id: str
) -> dict[str, object]:
    if from_user_id == to_user_id:
        raise HTTPException(400, "Cannot transfer host to yourself")

    try:
        room = await room_repo.get_room(room_id)
    except ResourceNotFoundError:
        raise HTTPException(404, "Room not found")

    if room.hostedBy != from_user_id:
        raise HTTPException(403, "Only the current host can transfer the room")

    try:
        membership = await membership_repo.get_room_membership(to_user_id, room_id)
    except ResourceNotFoundError:
        raise HTTPException(404, "Target user is not a member of this room")
    if membership.membershipStatus != MembershipStatus.ACTIVE:
        raise HTTPException(400, "Target user is not active in this room")

    if _get_transfer(room_id) is not None:
        raise HTTPException(409, "A host transfer is already pending")

    transfer: dict[str, object] = {
        "transferId": str(uuid.uuid4()),
        "fromUserId": from_user_id,
        "toUserId": to_user_id,
        "createdAt": _time_now(),
    }
    await room_service.refresh_room_state(room_id, "host_transfer_initiated")
    _set_transfer(room_id, transfer)
    return room_service.room_state_cache[room_id]


async def reject_transfer(
    room_id: str, transfer_id: str, user_id: str
) -> dict[str, object]:
    transfer = _get_transfer(room_id)
    if not transfer or transfer.get("transferId") != transfer_id:
        raise HTTPException(404, "Transfer not found")
    if transfer.get("toUserId") != user_id:
        raise HTTPException(403, "Only the invited user can reject this transfer")

    _set_transfer(room_id, None)
    await room_service.refresh_room_state(room_id, "host_transfer_rejected")
    return room_service.room_state_cache[room_id]



async def accept_transfer(
    room_id: str, transfer_id: str, user_id: str
) -> dict[str, object]:
    transfer = _get_transfer(room_id)
    if not transfer or transfer.get("transferId") != transfer_id:
        raise HTTPException(404, "Transfer not found")
    if transfer.get("toUserId") != user_id:
        raise HTTPException(403, "Only the invited user can accept this transfer")

    try:
        room = await room_repo.get_room(room_id)
    except ResourceNotFoundError:
        raise HTTPException(404, "Room not found")

    pa = await music_provider_repo.get_provider_account_by_user(
        user_id, room.supportedProviderId
    )
    if not pa or not pa.refreshToken:
        raise HTTPException(
            400, "Link your music provider account before accepting host transfer"
        )

    provider = get_provider_client(room.supportedProviderId)
    entries = await queue_entry_repo.get_queue_entries(room_id)

    removed_titles: list[str] = []
    playing_was_removed = False

    for entry in entries:
        track = await track_repo.get_track(entry.trackId)
        if track is None:
            await queue_entry_repo.update_queue_entry(
                entry.queueEntryId, {"status": QueueEntryStatus.REMOVED}
            )
            if entry.status == QueueEntryStatus.PLAYING:
                playing_was_removed = True
            continue

        try:
            match = await provider.find_track_for_user(
                user_id=user_id, title=track.title, artist=track.artist
            )
        except Exception:
            match = None

        if match is None:
            await queue_entry_repo.update_queue_entry(
                entry.queueEntryId, {"status": QueueEntryStatus.REMOVED}
            )
            removed_titles.append(f"{track.title} - {track.artist}")
            if entry.status == QueueEntryStatus.PLAYING:
                playing_was_removed = True
            continue

        if match.track_id and match.track_id != track.trackId:
            if await track_repo.get_track(match.track_id) is None:
                await track_repo.create_track(
                    {
                        "trackId": match.track_id,
                        "providerTrackId": match.provider_track_id,
                        "title": match.title,
                        "artist": match.artist,
                        "album": match.album,
                        "duration": match.duration,
                    }
                )
            await queue_entry_repo.update_queue_entry(
                entry.queueEntryId, {"trackId": match.track_id}
            )

    if playing_was_removed:
        await room_service._advance_to_next(room_id)

    await room_repo.update_host(room_id, user_id)
    await room_service.refresh_room_state(room_id, "host_transfer_completed")
    _set_transfer(room_id, None)

    if removed_titles:
        count = len(removed_titles)
        noun = "song" if count == 1 else "songs"
        _push_system_message(
            room_id,
            f"{count} {noun} removed during host transfer (not available on new host's account).",
        )

    return room_service.room_state_cache[room_id]
