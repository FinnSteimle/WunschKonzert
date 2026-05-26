from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.spotify_auth import router

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_spotify_login_endpoint(app):
    with (
        patch("services.room_service.register_or_update_user", new_callable=AsyncMock),
        patch(
            "services.providers.spotify_oauth.create_authorize_url",
            new_callable=AsyncMock,
        ) as mock_auth,
    ):
        mock_auth.return_value = "http://spotify.auth"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/auth/spotify/login?user_id=u1&return_to=/here")

        assert response.status_code == 200
        assert response.json()["auth_url"] == "http://spotify.auth"


@pytest.mark.asyncio
async def test_spotify_callback_error(app):
    mock_pending = {"return_to": "/here", "user_id": "u1"}
    with patch(
        "services.providers.spotify_oauth.validate_callback_state",
        new_callable=AsyncMock,
    ) as mock_val:
        mock_pending = {"return_to": "/here", "user_id": "u1"}
        mock_val.return_value = mock_pending

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get(
                "/auth/spotify/callback?state=st&error=access_denied",
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert "spotify_error=access_denied" in response.headers["location"]


@pytest.mark.asyncio
async def test_spotify_token_endpoint(app):
    with patch(
        "services.providers.spotify_oauth.get_user_access_token", new_callable=AsyncMock
    ) as mock_token:
        mock_auth_token = "token123"
        mock_token.return_value = mock_auth_token

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/auth/spotify/token?user_id=u1")

        assert response.status_code == 200
        assert response.json()["access_token"] == mock_auth_token


pytestmark = pytest.mark.unit
