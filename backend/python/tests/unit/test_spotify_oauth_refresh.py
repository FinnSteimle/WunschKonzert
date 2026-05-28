from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain import AccountStatus
from services.providers import spotify_oauth

pytestmark = pytest.mark.unit


def _provider_account(*, suspended: bool = False):
    pa = MagicMock()
    pa.providerAccountId = "pa-1"
    pa.refreshToken = "refresh-token"
    pa.accessToken = "expired-access"
    pa.tokenExpiresAt = datetime.now(UTC) - timedelta(minutes=1)
    pa.status = AccountStatus.SUSPENDED if suspended else AccountStatus.ACTIVE
    return pa


@pytest.mark.asyncio
async def test_get_user_access_token_suspended_returns_needs_relink():
    pa = _provider_account(suspended=True)
    with patch(
        "services.providers.spotify_oauth.music_provider_repo.get_provider_account_by_user",
        new_callable=AsyncMock,
        return_value=pa,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await spotify_oauth.get_user_access_token("user-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {"code": "needs_relink"}


@pytest.mark.asyncio
async def test_get_user_access_token_refresh_failure_suspends_account(monkeypatch):
    pa = _provider_account()

    class _FakeResponse:
        status_code = 400

        def json(self):
            return {}

    class _FakeClient:
        def __init__(self, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, headers: dict, data: dict):
            return _FakeResponse()

    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost/auth/spotify/callback")
    monkeypatch.setattr(
        "services.providers.spotify_oauth.httpx.AsyncClient", _FakeClient
    )

    suspend_mock = AsyncMock()
    with (
        patch(
            "services.providers.spotify_oauth.music_provider_repo.get_provider_account_by_user",
            new_callable=AsyncMock,
            return_value=pa,
        ),
        patch(
            "services.providers.spotify_oauth.music_provider_repo.suspend_provider_account",
            suspend_mock,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await spotify_oauth.get_user_access_token("user-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {"code": "needs_relink"}
    suspend_mock.assert_awaited_once_with("pa-1")
