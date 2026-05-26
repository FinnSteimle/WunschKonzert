import uuid

import pytest
from fastapi import HTTPException

from models import domain
from repositories import (
    membership_repo,
    music_provider_repo,
    room_repo,
    user_repo,
)
from services import room_service

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_delete_room(db_session, init_room):
    user_id = str(uuid.uuid4())
    room = await init_room(user_id=user_id)
    await room_service.delete_room(room.roomId, user_id)

    deleted_room = await room_repo.get_room(room.roomId)
    assert deleted_room.status == domain.RoomStatus.DELETED


# --- room_service.ensure_user_display_name() tests ---


@pytest.mark.asyncio
async def test_user_display_name_at_max_length(db_session):
    user_name = "a" * 60
    await room_service.ensure_user_display_name(str(uuid.uuid4()), user_name)


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
    user = await user_repo.get_user(user_id)
    assert user.displayName == "Alice"


# --- room_service.ensure_provider_exists() tests ---


@pytest.mark.asyncio
async def test_ensure_provider_exists_with_seeded_provider(db_session):
    provider_id = str(uuid.uuid4())
    await music_provider_repo.create_music_provider(provider_id, "Spotify")
    await room_service.ensure_provider_exists(provider_id)


@pytest.mark.asyncio
async def test_ensure_provider_exists_with_unknown_provider(db_session):
    fake_id = str(uuid.uuid4())
    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_provider_exists(fake_id)
    assert exc_info.value.status_code == 400
    assert "Unsupported music provider" in exc_info.value.detail


# --- room_service.ensure_active_membership() tests ---


@pytest.mark.asyncio
async def test_ensure_active_membership_creates_new(db_session, init_room):
    room = await init_room()
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "new_guest")
    await room_service.ensure_active_membership(user_id, room.roomId)
    membership = await membership_repo.get_room_membership(user_id, room.roomId)
    assert membership is not None
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_ensure_active_membership_reactivates_inactive(db_session, init_room):
    room = await init_room()
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "returning_guest")
    await membership_repo.create_room_membership(user_id, room.roomId)
    await membership_repo.leave_room(user_id, room.roomId)
    await room_service.ensure_active_membership(user_id, room.roomId)
    reactivated = await membership_repo.get_room_membership(user_id, room.roomId)
    assert reactivated.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_ensure_active_membership_already_active_is_noop(db_session, init_room):
    room = await init_room()
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "active_guest")
    await membership_repo.create_room_membership(user_id, room.roomId)
    await room_service.ensure_active_membership(user_id, room.roomId)
    memberships_list = await membership_repo.get_room_memberships(room.roomId)
    user_memberships = [m for m in memberships_list if m.userId == user_id]
    assert len(user_memberships) == 1


# --- room_service.leave_room() tests ---


@pytest.mark.asyncio
async def test_leave_room_success(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())
    await user_repo.create_user(guest_id, "guest")
    await membership_repo.create_room_membership(guest_id, room.roomId)
    state = await room_service.leave_room(room.roomId, guest_id)
    membership = await membership_repo.get_room_membership(guest_id, room.roomId)
    assert membership.membershipStatus == domain.MembershipStatus.INACTIVE
    assert state["lastActivity"]["type"] == "user_left"


@pytest.mark.asyncio
async def test_leave_room_host_raises_403(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.leave_room(room.roomId, room.hostedBy)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_leave_room_unknown_user_raises_error(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.leave_room(room.roomId, str(uuid.uuid4()))
    assert exc_info.value.status_code in (404, 500)


# --- room_service.join_room() tests ---


@pytest.mark.asyncio
async def test_join_room_success(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())
    result = await room_service.join_room(room.joinCode, guest_id, "NewGuest")
    assert result["success"] is True
    assert result["room_id"] == room.roomId
    membership = await membership_repo.get_room_membership(guest_id, room.roomId)
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_join_room_invalid_code_raises_422(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room("BAD!", str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_join_room_unknown_code_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room("ABCDE2", str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_join_room_empty_display_name_raises_400(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room(room.joinCode, str(uuid.uuid4()), "  ")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_join_deleted_room_raises_410(db_session, init_room):
    room = await init_room()
    await room_service.delete_room(room.roomId, room.hostedBy)
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room(room.joinCode, str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 410


# --- room_service.rename_participant() tests ---


@pytest.mark.asyncio
async def test_rename_participant_success(db_session, init_room):
    room = await init_room()
    await room_service.rename_participant(room.roomId, room.hostedBy, "NewName")
    user = await user_repo.get_user(room.hostedBy)
    assert user.displayName == "NewName"


@pytest.mark.asyncio
async def test_rename_participant_room_not_found_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.rename_participant(
            str(uuid.uuid4()), str(uuid.uuid4()), "Name"
        )
    assert exc_info.value.status_code == 404


# --- room_service.check_room_availability() tests ---


@pytest.mark.asyncio
async def test_check_room_availability_active_room(db_session, init_room):
    room = await init_room()
    available, unavailable = await room_service.check_room_availability([room.joinCode])
    assert room.joinCode in available


@pytest.mark.asyncio
async def test_check_room_availability_invalid_code(db_session):
    available, unavailable = await room_service.check_room_availability(["!!!"])
    assert "!!!" in unavailable
    assert available == []


@pytest.mark.asyncio
async def test_check_room_availability_duplicate_code(db_session, init_room):
    room = await init_room()
    available, unavailable = await room_service.check_room_availability(
        [room.joinCode, room.joinCode]
    )
    # First occurrence available, duplicate goes to unavailable
    assert available.count(room.joinCode) == 1
    assert room.joinCode in unavailable


@pytest.mark.asyncio
async def test_check_room_availability_deleted_room(db_session, init_room):
    room = await init_room()
    await room_service.delete_room(room.roomId, room.hostedBy)
    available, unavailable = await room_service.check_room_availability([room.joinCode])
    assert room.joinCode in unavailable
