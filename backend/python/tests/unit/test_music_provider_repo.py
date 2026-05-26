from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceExistsError
from repositories import music_provider_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_music_provider_auto_session():
    mock_session = AsyncMock()
    mock_provider = MagicMock()
    mock_session.get.return_value = mock_provider
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.music_provider_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        result = await music_provider_repo.get_music_provider("p1", session=None)
        assert result == mock_provider


@pytest.mark.asyncio
async def test_create_music_provider_already_exists():
    mock_session = AsyncMock()
    mock_session.get.return_value = MagicMock()

    with pytest.raises(ResourceExistsError):
        await music_provider_repo.create_music_provider(
            "p1", "Spotify", session=mock_session
        )


@pytest.mark.asyncio
async def test_create_provider_account_user_not_found():
    mock_session = AsyncMock()
    with patch("repositories.user_repo.get_user", return_value=None):
        with pytest.raises(ValueError, match="User not found"):
            await music_provider_repo.create_provider_account(
                "u1", "p1", "ext1", session=mock_session
            )


@pytest.mark.asyncio
async def test_create_provider_account_already_linked():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_session.execute.return_value = mock_result

    with patch("repositories.user_repo.get_user", return_value=MagicMock()):
        with pytest.raises(ValueError, match="User already has an account linked"):
            await music_provider_repo.create_provider_account(
                "u1", "p1", "ext1", session=mock_session
            )


@pytest.mark.asyncio
async def test_update_provider_account_tokens_not_found():
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    from datetime import UTC, datetime

    with pytest.raises(ValueError, match="Provider account not found"):
        await music_provider_repo.update_provider_account_tokens(
            "pa1", "token", datetime.now(UTC), session=mock_session
        )
