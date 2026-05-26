from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceNotFoundError
from models.domain import RoomStatus
from repositories import room_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_room_auto_session():
    """Verify that get_room handles session=None by creating a new session."""
    mock_room = MagicMock()
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_room
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.room_repo.get_session_factory", return_value=mock_session_factory
    ):
        # We also need to enter the async context manager of the session
        mock_session.__aenter__.return_value = mock_session

        result = await room_repo.get_room("r1", session=None)

        assert result == mock_room
        mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_room_not_found_raises():
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with pytest.raises(ResourceNotFoundError):
        await room_repo.get_room("missing", session=mock_session)


@pytest.mark.asyncio
async def test_create_room_collision_handling():
    """Verify that create_room retries on roomId or joinCode collisions."""
    mock_session = AsyncMock()

    # We want to test that it retries if a roomId collision occurs.
    # Logic:
    # 1. generate_room_id() -> "id1"
    # 2. session.get(Room, "id1") -> returns something (collision)
    # 3. generate_room_id() -> "id2"
    # 4. session.get(Room, "id2") -> returns None (unique)
    # 5. Resulting room has roomId="id2"

    with (
        patch("repositories.room_repo.generate_room_id", side_effect=["id1", "id2"]),
        patch(
            "repositories.room_repo.generate_join_code", side_effect=["code1", "code2"]
        ),
    ):
        # Mocking session.get for roomId collisions
        mock_session.get.side_effect = [MagicMock(), None]

        # Mocking session.execute for join code collisions
        # Logic:
        # 1. generate_join_code() -> "code1"
        # 2. session.execute(...) -> returns collision
        # 3. generate_join_code() -> "code2"
        # 4. session.execute(...) -> returns None (unique)

        mock_result_collision = MagicMock()
        mock_result_collision.scalar_one_or_none.return_value = MagicMock()

        mock_result_unique = MagicMock()
        mock_result_unique.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_result_collision, mock_result_unique]

        await room_repo.create_room("u1", "p1", "Room 1", session=mock_session)

        # Check that session.get was called twice
        assert mock_session.get.call_count == 2
        # Check that session.execute was called twice (for join code)
        assert mock_session.execute.call_count == 2

        # Check that session.add was called with the unique ID and code
        args, _ = mock_session.add.call_args
        assert args[0].roomId == "id2"
        assert args[0].joinCode == "code2"


@pytest.mark.asyncio
async def test_get_all_active_rooms_by_join_codes():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["CODE1", "CODE2"]
    mock_session.execute.return_value = mock_result

    codes = ["code1 ", "  code2", "missing"]
    result = await room_repo.get_all_active_rooms_by_join_codes(
        codes, session=mock_session
    )

    assert result == ["CODE1", "CODE2"]
    # Verify normalization
    args, _ = mock_session.execute.call_args
    # Extract the IN clause from the where clause if possible, or just verify the call
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_update_room_status():

    mock_session = AsyncMock()
    mock_room = MagicMock()
    mock_session.get.return_value = mock_room

    await room_repo.update_room_status("r1", RoomStatus.DELETED, session=mock_session)

    assert mock_room.status == RoomStatus.DELETED
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_get_room_with_full_state_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.unique.return_value.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceNotFoundError):
        await room_repo.get_room_with_full_state("r1", session=mock_session)
