from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.rooms import router

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_create_room_endpoint(app):
    """Verify that create_room endpoint calls service correctly."""
    mock_result = {
        "success": True,
        "message": "Success",
        "room_id": "r1",
        "join_code": "ABCDEF",
    }
    with patch(
        "services.room_service.create_room", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = mock_result

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/create_room",
                json={
                    "name": "My Room",
                    "user_id": "u1",
                    "display_name": "Me",
                    "supported_provider_id": "spotify",
                },
            )

        assert response.status_code == 200
        assert response.json() == mock_result
        mock_service.assert_called_once_with("My Room", "u1", "Me", "spotify")


@pytest.mark.asyncio
async def test_join_room_endpoint(app):
    mock_result = {
        "success": True,
        "message": "Success",
        "room_id": "r1",
        "join_code": "ABCDEF",
    }
    with (
        patch(
            "services.room_service.join_room", new_callable=AsyncMock
        ) as mock_service,
        patch("api.websockets.send_room_state", new_callable=AsyncMock) as mock_ws,
    ):
        mock_service.return_value = mock_result

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/join_room",
                json={"join_code": "ABCDEF", "user_id": "u1", "display_name": "Me"},
            )

        assert response.status_code == 200
        mock_service.assert_called_once_with("ABCDEF", "u1", "Me")
        mock_ws.assert_called_once_with("r1", force_refresh=True)


@pytest.mark.asyncio
async def test_rooms_availability_endpoint(app):
    mock_available = ["ABCDEF"]
    mock_unavailable = ["INVALID"]
    with patch(
        "services.room_service.check_room_availability", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = (mock_available, mock_unavailable)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/rooms/availability", json={"join_codes": ["ABCDEF", "INVALID"]}
            )

        assert response.status_code == 200
        assert response.json()["available_join_codes"] == mock_available
        assert response.json()["unavailable_join_codes"] == mock_unavailable
