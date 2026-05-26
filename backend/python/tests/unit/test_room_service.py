from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.exceptions import ResourceNotFoundError
from models.domain import MembershipStatus, RoomStatus
from services.room_service import (
    check_room_availability,
    create_room,
    delete_room,
    handle_disconnect,
    join_room,
    leave_room,
    register_or_update_user,
    rename_participant,
)
from services.room_state_service import JOIN_CODE_RE

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_leave_room_host_raises_403():
    mock_session = AsyncMock()
    mock_room = MagicMock(hostedBy="u1")
    with (
        patch("repositories.user_repo.get_user", return_value=MagicMock()),
        patch("repositories.room_repo.get_room", return_value=mock_room),
    ):
        with pytest.raises(HTTPException) as exc:
            await leave_room("r1", "u1", session=mock_session)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_handle_disconnect_not_found():
    mock_session = AsyncMock()
    with patch(
        "repositories.membership_repo.update_room_membership_status",
        side_effect=ResourceNotFoundError("Membership not found"),
    ):
        result = await handle_disconnect("r1", "u1", session=mock_session)
        assert result["success"] is True
        assert "No membership to disconnect" in result["message"]


@pytest.mark.asyncio
async def test_create_room_provider_not_linked_raises_403():
    mock_session = AsyncMock()
    with (
        patch("services.room_service.register_or_update_user", new_callable=AsyncMock),
        patch("services.room_service.ensure_provider_exists", new_callable=AsyncMock),
        patch(
            "repositories.music_provider_repo.get_provider_account_by_user",
            return_value=None,
        ),
        patch("services.room_service.is_account_linked", return_value=False),
    ):
        with pytest.raises(HTTPException) as exc:
            await create_room("Room", "u1", "Me", "spotify", session=mock_session)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_join_room_invalid_code_raises_422():
    with pytest.raises(HTTPException) as exc:
        await join_room("invalid", "u1", "Me", session=AsyncMock())
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_room_non_host_raises_403():
    mock_session = AsyncMock()
    mock_room = MagicMock(hostedBy="host")
    with patch("repositories.room_repo.get_room", return_value=mock_room):
        with pytest.raises(HTTPException) as exc:
            await delete_room("r1", "not_host", session=mock_session)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_rename_participant_inactive_raises_403():
    mock_session = AsyncMock()
    mock_membership = MagicMock(membershipStatus=MembershipStatus.INACTIVE)
    with (
        patch("repositories.room_repo.get_room", return_value=MagicMock()),
        patch(
            "repositories.membership_repo.get_room_membership",
            return_value=mock_membership,
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await rename_participant("r1", "u1", "New Name", session=mock_session)
        assert exc.value.status_code == 403


def test_join_code_regex_valid():
    assert JOIN_CODE_RE.match("ABCDE2")
    assert JOIN_CODE_RE.match("987654")
    assert JOIN_CODE_RE.match("ZXYWVK")


def test_join_code_regex_invalid():
    # Too short
    assert not JOIN_CODE_RE.match("ABC12")
    # Too long
    assert not JOIN_CODE_RE.match("ABC1234")
    # Forbidden characters (0, 1, I, O)
    assert not JOIN_CODE_RE.match("ABCIO1")
    # Special characters
    assert not JOIN_CODE_RE.match("ABC-12")


@pytest.mark.asyncio
async def test_register_or_update_user_empty_raises():
    with pytest.raises(HTTPException) as exc:
        await register_or_update_user("u1", "   ")
    assert exc.value.status_code == 400
    assert "required" in exc.value.detail


@pytest.mark.asyncio
async def test_register_or_update_user_too_long_raises():
    with pytest.raises(HTTPException) as exc:
        await register_or_update_user("u1", "a" * 61)
    assert exc.value.status_code == 400
    assert "too long" in exc.value.detail


@pytest.mark.asyncio
async def test_register_or_update_user_creates_if_missing():
    mock_session = AsyncMock()
    with patch(
        "repositories.user_repo.get_user", side_effect=ResourceNotFoundError("msg")
    ):
        with patch(
            "repositories.user_repo.create_user", new_callable=AsyncMock
        ) as mock_create:
            await register_or_update_user("u1", "New User", session=mock_session)
            mock_create.assert_called_with("u1", "New User", session=mock_session)


@pytest.mark.asyncio
async def test_register_or_update_user_updates_if_exists():
    mock_session = AsyncMock()
    mock_user = MagicMock()
    with patch("repositories.user_repo.get_user", return_value=mock_user):
        with patch(
            "repositories.user_repo.update_user_display_name", new_callable=AsyncMock
        ) as mock_update:
            await register_or_update_user("u1", "Updated Name", session=mock_session)
            mock_update.assert_called_with("u1", "Updated Name", session=mock_session)


@pytest.mark.asyncio
async def test_join_room_logic_normalizes_code():
    """Verify that ' abc-123 ' is not valid, but ' abcde2 ' becomes 'ABCDE2' and is valid."""
    mock_session = AsyncMock()

    # 1. Test invalid code (regex failure)
    with pytest.raises(HTTPException) as exc:
        await join_room(" abc-123 ", "u1", "Name", session=mock_session)
    assert exc.value.status_code == 422

    # 2. Test valid code normalization

    mock_room = MagicMock(roomId="r1", joinCode="ABCDE2", status=RoomStatus.ACTIVE)

    with patch("services.room_service.register_or_update_user", new_callable=AsyncMock):
        with patch(
            "repositories.room_repo.get_room_by_join_code", return_value=mock_room
        ) as mock_get_room:
            with patch(
                "services.room_service.ensure_active_membership", new_callable=AsyncMock
            ):
                with patch(
                    "services.room_service.refresh_room_state", new_callable=AsyncMock
                ):
                    with patch(
                        "services.room_service.build_last_activity",
                        new_callable=AsyncMock,
                    ):
                        await join_room(" abcde2 ", "u1", "Name", session=mock_session)

                        # Verify the code was stripped and uppercased
                        mock_get_room.assert_called_with("ABCDE2", session=mock_session)


@pytest.mark.asyncio
async def test_check_room_availability_logic():
    """Test unique filtering and normalization without hitting the repo."""
    # We only mock the repository call at the end
    with patch(
        "repositories.room_repo.get_all_active_rooms_by_join_codes",
        return_value=["ABCDE2"],
    ) as mock_repo:
        available, unavailable = await check_room_availability(
            [" abcde2 ", "ABCDE2", "invalid"]
        )

        # ' abcde2 ' and 'ABCDE2' are duplicates. Only 'ABCDE2' should be sent to repo.
        # 'invalid' fails regex.
        mock_repo.assert_called_with(["ABCDE2"])

        assert "ABCDE2" in available
        assert "INVALID" in unavailable  # Uppercased invalid code
