from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.membership_repo as membership_repo
import repositories.music_provider_repo as music_provider_repo
import repositories.room_repo as room_repo
import repositories.user_repo as user_repo
from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import (
    MembershipStatus,
    RoomMembership,
    RoomStatus,
)
from services.providers.account_status import is_account_linked
from services.room_state_service import (
    JOIN_CODE_RE,
    build_last_activity,
    refresh_room_state,
)


async def leave_room(
    room_id: str, user_id: str, session: AsyncSession | None = None
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await leave_room(room_id, user_id, session=new_session)
            await new_session.commit()
            return result

    try:
        try:
            await user_repo.get_user(user_id, session=session)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            room = await room_repo.get_room(room_id, session=session)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="Room not found")

        if room.hostedBy == user_id:
            raise HTTPException(
                status_code=403,
                detail="Hosts cannot leave the room. Please delete the room instead.",
            )

        await membership_repo.leave_room(user_id, room_id, session=session)
        activity = await build_last_activity("user_left", user_id, session)
        return await refresh_room_state(
            room_id,
            "participant_left",
            session=session,
            last_activity=activity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


async def handle_disconnect(
    room_id: str, user_id: str, session: AsyncSession | None = None
) -> dict[str, object]:
    """Handle a participant's disconnect by marking them as inactive."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await handle_disconnect(room_id, user_id, session=new_session)
            await new_session.commit()
            return result

    try:
        await membership_repo.update_room_membership_status(
            user_id, room_id, MembershipStatus.INACTIVE, session=session
        )
        return await refresh_room_state(
            room_id,
            "participant_disconnected",
            session=session,
        )
    except ResourceNotFoundError:
        # If no membership was found, nothing to do.
        return {"success": True, "message": "No membership to disconnect"}
    except Exception as e:
        print(f"Error handling disconnect for user {user_id} in room {room_id}: {e}")
        return {"success": False, "message": str(e)}


async def create_room(
    name: str,
    user_id: str,
    display_name: str,
    supported_provider_id: str,
    session: AsyncSession | None = None,
) -> dict[str, object]:
    """Create a new room, validating user and provider."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await create_room(
                name, user_id, display_name, supported_provider_id, session=new_session
            )
            await new_session.commit()
            return result

    await register_or_update_user(user_id, display_name, session=session)
    await ensure_provider_exists(supported_provider_id, session=session)

    pa = await music_provider_repo.get_provider_account_by_user(
        user_id, supported_provider_id, session=session
    )
    if not is_account_linked(supported_provider_id, pa):
        raise HTTPException(
            status_code=403,
            detail=f"You must link your {supported_provider_id} account before creating a room",
        )

    try:
        room = await room_repo.create_room(
            user_id,
            supported_provider_id,
            name,
            session=session,
        )
        await ensure_active_membership(user_id, room.roomId, session=session)
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


async def join_room(
    join_code: str, user_id: str, display_name: str, session: AsyncSession | None = None
) -> dict[str, object]:
    """Validate and join a room by its join code."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await join_room(
                join_code, user_id, display_name, session=new_session
            )
            await new_session.commit()
            return result

    if display_name is None or not display_name.strip():
        raise HTTPException(status_code=400, detail="Display name is required")

    normalized_code = join_code.strip().upper()
    if not JOIN_CODE_RE.match(normalized_code):
        raise HTTPException(
            status_code=422,
            detail="Join code must be exactly 6 characters (A-Z, 2-9, no I/O/0/1).",
        )

    await register_or_update_user(user_id, display_name, session=session)

    try:
        room = await room_repo.get_room_by_join_code(normalized_code, session=session)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(
            status_code=410,
            detail="This session has ended and is no longer available.",
        )

    try:
        await ensure_active_membership(user_id, room.roomId, session=session)
        activity = await build_last_activity("user_joined", user_id, session)
        await refresh_room_state(
            room.roomId,
            "participant_joined",
            session=session,
            last_activity=activity,
        )
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


async def delete_room(
    room_id: str, user_id: str, session: AsyncSession | None = None
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await delete_room(room_id, user_id, session=new_session)
            await new_session.commit()
            return result

    try:
        # Get room and validate
        room = await room_repo.get_room(room_id, session=session)
        if room.hostedBy != user_id:
            raise HTTPException(status_code=403, detail="Only host can delete room")

        # Update room status
        await room_repo.update_room_status(room_id, RoomStatus.DELETED, session=session)

        # Update all memberships
        membership_stmt = select(RoomMembership).where(RoomMembership.roomId == room_id)
        membership_result = await session.execute(membership_stmt)
        memberships_list = membership_result.scalars().all()

        for membership in memberships_list:
            membership.membershipStatus = MembershipStatus.INACTIVE
            if membership.leftAt is None:
                membership.leftAt = datetime.now(UTC).replace(tzinfo=None)

        return {"success": True, "message": "Room deleted"}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Room not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to delete room: {str(e)}")


async def register_or_update_user(
    user_id: str, display_name: str, session: AsyncSession | None = None
) -> None:
    trimmed = display_name.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Display name is required")
    if len(trimmed) > 60:
        raise HTTPException(status_code=400, detail="Display name is too long")

    user_exists = True
    try:
        await user_repo.get_user(user_id, session=session)
    except ResourceNotFoundError:
        user_exists = False

    if not user_exists:
        try:
            await user_repo.create_user(user_id, trimmed, session=session)
            return
        except ValueError as e:
            if "already exists" not in str(e):
                raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        await user_repo.update_user_display_name(user_id, trimmed, session=session)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


async def ensure_provider_exists(
    provider_id: str, session: AsyncSession | None = None
) -> None:
    try:
        await music_provider_repo.get_music_provider(provider_id, session=session)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=400, detail=f"Unsupported music provider: {provider_id}. "
        )


async def ensure_active_membership(
    user_id: str, room_id: str, session: AsyncSession | None = None
) -> None:
    try:
        await membership_repo.update_room_membership_status(
            user_id, room_id, MembershipStatus.ACTIVE, session=session
        )
    except ResourceNotFoundError:
        # Membership doesn't exist, create it
        await membership_repo.create_room_membership(user_id, room_id, session=session)


async def rename_participant(
    room_id: str, user_id: str, display_name: str, session: AsyncSession | None = None
) -> dict[str, object]:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await rename_participant(
                room_id, user_id, display_name, session=new_session
            )
            await new_session.commit()
            return result

    try:
        try:
            await room_repo.get_room(room_id, session=session)
        except ResourceNotFoundError:
            raise HTTPException(status_code=404, detail="Room not found")

        try:
            membership = await membership_repo.get_room_membership(
                user_id, room_id, session=session
            )
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=403, detail="Only active room participants can rename"
            )

        if membership.membershipStatus != MembershipStatus.ACTIVE:
            raise HTTPException(
                status_code=403, detail="Only active room participants can rename"
            )

        await register_or_update_user(user_id, display_name, session=session)
        activity = await build_last_activity("user_renamed", user_id, session)
        return await refresh_room_state(
            room_id,
            "participant_renamed",
            session=session,
            last_activity=activity,
        )
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
