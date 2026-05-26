from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.auth import router

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_auth_account_endpoint(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/auth/account", json={"username": "u1", "password": "p1"}
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "token" in response.json()


@pytest.mark.asyncio
async def test_add_music_provider_endpoint(app):
    mock_pa = MagicMock(providerAccountId="pa1")
    with (
        patch("repositories.user_repo.get_user", return_value=MagicMock()),
        patch(
            "repositories.music_provider_repo.create_provider_account",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        mock_create.return_value = mock_pa

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/add_music_provider",
                json={
                    "user_id": "u1",
                    "provider_id": "spotify",
                    "external_user_id": "ext1",
                },
            )

        assert response.status_code == 200
        assert response.json()["provider_account_id"] == "pa1"
