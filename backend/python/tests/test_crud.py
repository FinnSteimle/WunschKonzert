import uuid

import pytest

from core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
)
from models import domain
from repositories import crud


@pytest.mark.asyncio
async def test_create_and_get_user_base_case(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name, db_session)
    user: domain.User = await crud.get_user(user_id, db_session)

    assert user.userId == user_id
    assert user.displayName == display_name


@pytest.mark.asyncio
async def test_create_user_that_exists_throws_error(db_session):
    user_id = str(uuid.uuid4())
    display_name = "test_user"

    await crud.create_user(user_id, display_name, db_session)

    with pytest.raises(ResourceExistsError):
        await crud.create_user(user_id, display_name, db_session)


@pytest.mark.asyncio
async def test_create_and_get_music_provider(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await crud.create_music_provider(provider_id, name, db_session)
    provider: domain.MusicProvider = await crud.get_music_provider(
        provider_id, db_session
    )

    assert provider.providerId == provider_id
    assert provider.name == name


@pytest.mark.asyncio
async def test_create_provider_that_exists_throws_error(db_session):
    provider_id = str(uuid.uuid4())
    name = "test_provider"

    await crud.create_music_provider(provider_id, name, db_session)

    with pytest.raises(ResourceExistsError):
        await crud.create_music_provider(provider_id, name, db_session)


@pytest.mark.asyncio
async def test_create_room(db_session):
    user_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    await crud.create_user(user_id, "host", db_session)
    await crud.create_music_provider(provider_id, "Spotify", db_session)
    await db_session.flush()

    room = await crud.create_room(user_id, provider_id, "My Custom Room", db_session)

    assert room.name == "My Custom Room"
    assert room.hostedBy == user_id
    assert room.supportedProviderId == provider_id
    assert room.joinCode is not None


@pytest.mark.asyncio
async def test_create_room_with_default_name(db_session):
    user_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    await crud.create_user(user_id, "host", db_session)
    await crud.create_music_provider(provider_id, "Spotify", db_session)
    await db_session.flush()

    room = await crud.create_room(user_id, provider_id, session=db_session)

    assert room.name == f"Room_{room.joinCode}"
    assert room.hostedBy == user_id


@pytest.mark.asyncio
async def test_get_room_by_join_code(db_session, init_room):
    room = await init_room()

    room_by_code = await crud.get_room_by_join_code(room.joinCode)
    assert room_by_code is not None
    assert room_by_code.roomId == room.roomId
    assert len(room.joinCode) == 6


@pytest.mark.asyncio
async def test_get_room_by_join_code_not_found(db_session, init_room):
    await init_room()

    with pytest.raises(ResourceNotFoundError):
        await crud.get_room_by_join_code("invalid_code")


# Delete room test is in test_services.py since it uses services for deletion and not crud directly


@pytest.mark.asyncio
async def test_membership(db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    memberships = await crud.get_room_memberships(room.roomId)
    assert len(memberships) == 1
    assert memberships[0].userId == host_id


@pytest.mark.asyncio
async def test_adding_user_to_room(db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "guest")
    await crud.create_room_membership(user_id, room.roomId)

    memberships = await crud.get_room_memberships(room.roomId)
    member_ids = [m.userId for m in memberships]
    assert len(memberships) == 2
    assert user_id in member_ids
    assert host_id in member_ids


@pytest.mark.asyncio
async def test_adding_multiple_users_to_room(db_session, init_room):
    """Verify several users can join a room. Keep count low (5) to avoid
    opening dozens of DB sessions — capacity testing belongs in integration tests."""
    total_users = 5
    members = []
    host_id = str(uuid.uuid4())
    room: domain.Room = await init_room(user_id=host_id)

    for i in range(total_users - 1):
        user_id = str(uuid.uuid4())
        members.append(user_id)
        await crud.create_user(user_id, f"guest{i + 1}")
        await crud.create_room_membership(user_id, room.roomId)

    memberships = await crud.get_room_memberships(room.roomId)
    member_ids = [m.userId for m in memberships]
    assert len(memberships) == total_users
    assert all(m in member_ids for m in members)
    assert host_id in member_ids
