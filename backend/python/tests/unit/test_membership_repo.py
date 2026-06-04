from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceExistsError, ResourceNotFoundError
from models.domain import MembershipStatus
from repositories import membership_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_room_membership_auto_session():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_membership = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_membership
    mock_session.execute.return_value = mock_result
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.membership_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        result = await membership_repo.get_room_membership("u1", "r1", session=None)
        assert result == mock_membership


@pytest.mark.asyncio
async def test_create_room_membership_already_exists():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceExistsError):
        await membership_repo.create_room_membership("u1", "r1", session=mock_session)


@pytest.mark.asyncio
async def test_leave_room_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceNotFoundError):
        await membership_repo.leave_room("u1", "r1", session=mock_session)


@pytest.mark.asyncio
async def test_get_room_active_memberships():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("membership", "user")]
    mock_session.execute.return_value = mock_result

    result = await membership_repo.get_room_active_memberships(
        "r1", session=mock_session
    )
    assert result == [("membership", "user")]


@pytest.mark.asyncio
async def test_update_room_membership_status_active():

    mock_session = AsyncMock()
    mock_membership = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_membership
    mock_session.execute.return_value = mock_result

    result = await membership_repo.update_room_membership_status(
        "u1", "r1", MembershipStatus.ACTIVE, session=mock_session
    )

    assert result.membershipStatus == MembershipStatus.ACTIVE
    assert result.leftAt is None
    assert result.joinedAt is not None
