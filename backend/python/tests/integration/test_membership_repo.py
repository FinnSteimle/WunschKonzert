import uuid

import pytest

from repositories import membership_repo, user_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_membership(db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    memberships_list = await membership_repo.get_room_memberships(room.roomId)
    assert len(memberships_list) == 1
    assert memberships_list[0].userId == host_id


@pytest.mark.asyncio
async def test_adding_user_to_room(db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "guest")
    await membership_repo.create_room_membership(user_id, room.roomId)

    memberships_list = await membership_repo.get_room_memberships(room.roomId)
    member_ids = [m.userId for m in memberships_list]
    assert len(memberships_list) == 2
    assert user_id in member_ids
    assert host_id in member_ids


@pytest.mark.asyncio
async def test_adding_multiple_users_to_room(db_session, init_room):
    """Verify several users can join a room. Keep count low (5) to avoid
    opening dozens of DB sessions; capacity testing belongs in integration tests."""
    total_users = 5
    members = []
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    for i in range(total_users - 1):
        user_id = str(uuid.uuid4())
        members.append(user_id)
        await user_repo.create_user(user_id, f"guest{i + 1}")
        await membership_repo.create_room_membership(user_id, room.roomId)

    memberships_list = await membership_repo.get_room_memberships(room.roomId)
    member_ids = [m.userId for m in memberships_list]
    assert len(memberships_list) == total_users
    assert all(m in member_ids for m in members)
    assert host_id in member_ids
