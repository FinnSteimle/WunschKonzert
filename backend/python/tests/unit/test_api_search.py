from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.provider_search import router
from models.domain import RoomStatus

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_search_tracks_endpoint(app):
    # Use a real Room object but with mocked attributes if needed,
    # or just a better MagicMock
    mock_room = MagicMock()
    mock_room.status = RoomStatus.ACTIVE
    mock_room.supportedProviderId = "spotify"
    mock_room.hostedBy = "u1"

    mock_track = MagicMock()
    mock_track.to_api_dict.return_value = {"title": "Song"}

    mock_provider = MagicMock()
    mock_provider.provider_id = "spotify"
    mock_provider.search_tracks = AsyncMock(return_value=[mock_track])

    # Using 'api.routers.provider_search.room_repo.get_room' to be sure
    with (
        patch(
            "api.routers.provider_search.room_repo.get_room", new_callable=AsyncMock
        ) as mock_get_room,
        patch(
            "api.routers.provider_search.get_provider_client",
            return_value=mock_provider,
        ),
    ):
        mock_get_room.return_value = mock_room

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/rooms/r1/search?q=query")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "spotify"
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["title"] == "Song"


@pytest.mark.asyncio
async def test_search_tracks_inactive_room(app):
    mock_room = MagicMock()
    mock_room.status = RoomStatus.DELETED

    with patch(
        "api.routers.provider_search.room_repo.get_room", new_callable=AsyncMock
    ) as mock_get_room:
        mock_get_room.return_value = mock_room
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/rooms/r1/search?q=query")

        assert response.status_code == 400
        assert "is not active" in response.json()["detail"]
