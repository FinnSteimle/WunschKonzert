from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repositories import track_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_track_auto_session():
    mock_session = AsyncMock()
    mock_track = MagicMock()
    mock_session.get.return_value = mock_track
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.track_repo.get_session_factory", return_value=mock_session_factory
    ):
        mock_session.__aenter__.return_value = mock_session
        result = await track_repo.get_track("t1", session=None)
        assert result == mock_track


@pytest.mark.asyncio
async def test_create_track():
    mock_session = AsyncMock()
    track_data = {"trackId": "t1", "title": "Song", "artist": "Artist"}

    await track_repo.create_track(track_data, session=mock_session)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
