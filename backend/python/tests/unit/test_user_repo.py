from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceExistsError, ResourceNotFoundError
from repositories import user_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_user_auto_session():
    mock_session = AsyncMock()
    mock_user = MagicMock()
    mock_session.get.return_value = mock_user
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.user_repo.get_session_factory", return_value=mock_session_factory
    ):
        mock_session.__aenter__.return_value = mock_session
        result = await user_repo.get_user("u1", session=None)
        assert result == mock_user


@pytest.mark.asyncio
async def test_create_user_already_exists():
    mock_session = AsyncMock()
    mock_session.get.return_value = MagicMock()

    with pytest.raises(ResourceExistsError):
        await user_repo.create_user("u1", "Display Name", session=mock_session)


@pytest.mark.asyncio
async def test_update_user_display_name_not_found():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceNotFoundError):
        await user_repo.update_user_display_name("u1", "New Name", session=mock_session)
