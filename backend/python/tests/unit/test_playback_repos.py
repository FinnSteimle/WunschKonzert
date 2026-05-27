from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from repositories import playback_history_repo, playback_session_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_current_playback_session_auto_session():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.playback_session_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        await playback_session_repo.get_current_playback_session("r1", session=None)
        mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_playback_session_not_found():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = None

    with pytest.raises(ResourceNotFoundError):
        await playback_session_repo.update_playback_session(
            "ps1", {"state": "playing"}, session=mock_session
        )


@pytest.mark.asyncio
async def test_add_history_entry_auto_session():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.playback_history_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        await playback_history_repo.add_history_entry({"roomId": "r1"}, session=None)
        mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_history_auto_session():
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.playback_history_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        await playback_history_repo.get_history("r1", session=None)
        mock_session.execute.assert_called_once()
