from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceNotFoundError
from repositories import queue_entry_repo

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_queue_entries_auto_session():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["entry1"]
    mock_session.execute.return_value = mock_result
    mock_session_factory = MagicMock(return_value=mock_session)

    with patch(
        "repositories.queue_entry_repo.get_session_factory",
        return_value=mock_session_factory,
    ):
        mock_session.__aenter__.return_value = mock_session
        result = await queue_entry_repo.get_queue_entries("r1", session=None)
        assert result == ["entry1"]


@pytest.mark.asyncio
async def test_update_queue_entry_not_found():
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    with pytest.raises(ResourceNotFoundError):
        await queue_entry_repo.update_queue_entry(
            "qe1", {"status": "REMOVED"}, session=mock_session
        )


@pytest.mark.asyncio
async def test_get_max_queue_position():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 5
    mock_session.execute.return_value = mock_result

    result = await queue_entry_repo.get_max_queue_position("r1", session=mock_session)
    assert result == 5


@pytest.mark.asyncio
async def test_get_max_queue_position_empty():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await queue_entry_repo.get_max_queue_position("r1", session=mock_session)
    assert result == 0


@pytest.mark.asyncio
async def test_get_next_queued_entry():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_entry = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_entry
    mock_session.execute.return_value = mock_result

    result = await queue_entry_repo.get_next_queued_entry("r1", session=mock_session)
    assert result == mock_entry
