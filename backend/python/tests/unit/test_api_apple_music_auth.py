from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.apple_music_auth import router

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_apple_music_developer_token_endpoint(app):
    with patch(
        "api.routers.apple_music_auth.get_developer_token", new_callable=AsyncMock
    ) as mock_dev:
        mock_dev.return_value = "dev-token-123"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/auth/apple-music/developer-token?user_id=u1")

        assert response.status_code == 200
        assert response.json()["developer_token"] == "dev-token-123"
        mock_dev.assert_awaited_once()


@pytest.mark.asyncio
async def test_apple_music_token_not_linked(app):
    with patch(
        "repositories.music_provider_repo.get_provider_account_by_user",
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/auth/apple-music/token?user_id=u1")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "not_linked"


@pytest.mark.asyncio
async def test_apple_music_profile_linked(app):
    mock_pa = MagicMock()
    mock_pa.storefront = "us"
    mock_pa.status = "active"

    with (
        patch(
            "repositories.music_provider_repo.get_provider_account_by_user",
            return_value=mock_pa,
        ),
        patch("repositories.user_repo.get_user", new_callable=AsyncMock) as mock_user,
    ):
        mock_user.return_value = MagicMock(displayName="Apple User")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/auth/apple-music/profile?user_id=u1")

        assert response.status_code == 200
        data = response.json()
        assert data["linked"] is True
        assert data["storefront"] == "us"
        assert data["display_name"] == "Apple User"
