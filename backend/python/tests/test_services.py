import uuid

import pytest
from fastapi import HTTPException

from core.exceptions import (
    ResourceExistsError,
)
from models import domain
from repositories import crud
from services import room_service


@pytest.mark.asyncio
async def test_delete_room(db_session, init_room):
    user_id = str(uuid.uuid4())
    room = await init_room(user_id=user_id)
    await room_service.delete_room_service(room.roomId, user_id)

    deleted_room = await crud.get_room(room.roomId)
    assert deleted_room.status == domain.RoomStatus.DELETED


#
# --- room_service.ensure_user_display_name() tests ---
#
@pytest.mark.asyncio
async def test_user_display_name_at_max_length(db_session):
    user_name = "a" * 60
    await room_service.ensure_user_display_name(str(uuid.uuid4()), user_name)
    # no exception → pass

@pytest.mark.asyncio
async def test_user_display_name_above_max_length(db_session):
    user_name = "a" * 61
    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_user_display_name(str(uuid.uuid4()), user_name)
    assert exc_info.value.status_code == 400
    assert "too long" in exc_info.value.detail

@pytest.mark.asyncio
async def test_user_display_name_empty_raises(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_user_display_name(str(uuid.uuid4()), "   ")
    assert exc_info.value.status_code == 400
    assert "required" in exc_info.value.detail

@pytest.mark.asyncio
async def test_user_display_name_strips_whitespace(db_session):
    user_id = str(uuid.uuid4())
    await room_service.ensure_user_display_name(user_id, "  Alice  ")
    user = await crud.get_user(user_id)
    assert user.displayName == "Alice"


#
# --- room_service.ensure_provider_exists() tests ---
#
@pytest.mark.asyncio
async def test_ensure_provider_exists_with_seeded_provider(db_session):
    provider_id = str(uuid.uuid4())
    await crud.create_music_provider(provider_id, "Spotify")

    # Should not raise
    await room_service.ensure_provider_exists(provider_id)


@pytest.mark.asyncio
async def test_ensure_provider_exists_with_unknown_provider(db_session):
    fake_id = str(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_provider_exists(fake_id)
    assert exc_info.value.status_code == 400
    assert "Unsupported music provider" in exc_info.value.detail


#
# --- room_service.ensure_active_membership() tests ---
#
@pytest.mark.asyncio
async def test_ensure_active_membership_creates_new(db_session, init_room):
    """User with no prior membership gets one created."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "new_guest")

    await room_service.ensure_active_membership(user_id, room.roomId)

    membership = await crud.get_room_membership(user_id, room.roomId)
    assert membership is not None
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_ensure_active_membership_reactivates_inactive(db_session, init_room):
    """User who left the room gets reactivated instead of duplicated."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "returning_guest")
    await crud.create_room_membership(user_id, room.roomId)

    # Simulate leaving
    await crud.leave_room(user_id, room.roomId)
    left = await crud.get_room_membership(user_id, room.roomId)
    assert left.membershipStatus == domain.MembershipStatus.INACTIVE

    # Rejoin
    await room_service.ensure_active_membership(user_id, room.roomId)

    reactivated = await crud.get_room_membership(user_id, room.roomId)
    assert reactivated.membershipStatus == domain.MembershipStatus.ACTIVE
    assert reactivated.leftAt is None


@pytest.mark.asyncio
async def test_ensure_active_membership_already_active_is_noop(db_session, init_room):
    """Calling on an already-active member doesn't error or duplicate."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "active_guest")
    await crud.create_room_membership(user_id, room.roomId)

    # Should not raise
    await room_service.ensure_active_membership(user_id, room.roomId)

    memberships = await crud.get_room_memberships(room.roomId)
    user_memberships = [m for m in memberships if m.userId == user_id]
    assert len(user_memberships) == 1
    assert user_memberships[0].membershipStatus == domain.MembershipStatus.ACTIVE
