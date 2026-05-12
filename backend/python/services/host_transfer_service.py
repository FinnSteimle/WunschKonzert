from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

import repositories.membership_repo as membership_repo
import repositories.room_repo as room_repo
import services.room_service as room_service
from core.exceptions import ResourceNotFoundError
from models.domain import MembershipStatus

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
    messages.append(
        {"id": str(uuid.uuid4()), "text": text, "at": _time_now()}
    )
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
