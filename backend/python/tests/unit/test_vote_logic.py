from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from services.vote_service import vote_queue_entry


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400():
    with pytest.raises(HTTPException) as exc:
        # We don't even need to mock the session if validation happens first
        await vote_queue_entry("r1", "qe1", "u1", "sideways", session=AsyncMock())
    assert exc.value.status_code == 400
    assert "Invalid vote type" in exc.value.detail


@pytest.mark.asyncio
async def test_vote_replay_on_non_playing_raises_400():
    # Mocking the repository to return a queued entry instead of playing
    mock_entry = AsyncMock()
    mock_entry.status.value = "queued"
    mock_entry.roomId = "r1"

    with patch(
        "repositories.queue_entry_repo.get_queue_entry", return_value=mock_entry
    ):
        with pytest.raises(HTTPException) as exc:
            await vote_queue_entry("r1", "qe1", "u1", "replay", session=AsyncMock())
        assert exc.value.status_code == 400
        assert "only be cast on the currently playing song" in exc.value.detail
