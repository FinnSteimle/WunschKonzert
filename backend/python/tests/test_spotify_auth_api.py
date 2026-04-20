import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from api.routers import spotify_auth
from repositories import crud, user_repo


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload


class _SequencedAsyncClient:
    post_responses: list[_FakeResponse] = []
    get_responses: list[_FakeResponse] = []

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict[str, str], data: dict[str, str]):
        assert url == "https://accounts.spotify.com/api/token"
        assert headers["Authorization"].startswith("Basic ")
        assert data["grant_type"] in {"authorization_code", "refresh_token"}
        if not _SequencedAsyncClient.post_responses:
            raise AssertionError("Unexpected POST call to Spotify token endpoint")
        return _SequencedAsyncClient.post_responses.pop(0)

    async def get(self, url: str, headers: dict[str, str]):
        assert url == "https://api.spotify.com/v1/me"
        assert headers["Authorization"].startswith("Bearer ")
        if not _SequencedAsyncClient.get_responses:
            raise AssertionError("Unexpected GET call to Spotify profile endpoint")
        return _SequencedAsyncClient.get_responses.pop(0)


@pytest.fixture(autouse=True)
def _reset_spotify_state(monkeypatch):
    spotify_auth._pending_states.clear()
    _SequencedAsyncClient.post_responses = []
    _SequencedAsyncClient.get_responses = []
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "http://localhost/auth/spotify/callback")
    yield
    spotify_auth._pending_states.clear()


@pytest.mark.asyncio
async def test_spotify_login_returns_auth_url_and_persists_state(client):
    user_id = str(uuid.uuid4())
    return_to = "http://localhost/create"

    response = await client.get(
        "/auth/spotify/login",
        params={"user_id": user_id, "return_to": return_to},
    )

    assert response.status_code == 200
    auth_url = response.json()["auth_url"]
    parsed = urlparse(auth_url)
    query = parse_qs(parsed.query)
    state = query["state"][0]

    assert parsed.netloc == "accounts.spotify.com"
    assert query["client_id"][0] == "client-id"
    assert query["redirect_uri"][0] == "http://localhost/auth/spotify/callback"
    assert spotify_auth._pending_states[state]["user_id"] == user_id
    assert spotify_auth._pending_states[state]["return_to"] == return_to


@pytest.mark.asyncio
async def test_spotify_login_missing_credentials_returns_503(client, monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)

    response = await client.get(
        "/auth/spotify/login",
        params={"user_id": str(uuid.uuid4()), "return_to": "http://localhost/create"},
    )

    assert response.status_code == 503
    assert "credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_spotify_login_missing_redirect_uri_returns_503(client, monkeypatch):
    monkeypatch.delenv("SPOTIFY_REDIRECT_URI", raising=False)

    response = await client.get(
        "/auth/spotify/login",
        params={"user_id": str(uuid.uuid4()), "return_to": "http://localhost/create"},
    )

    assert response.status_code == 503
    assert "SPOTIFY_REDIRECT_URI" in response.json()["detail"]


@pytest.mark.asyncio
async def test_spotify_callback_invalid_state_returns_400(client):
    response = await client.get(
        "/auth/spotify/callback",
        params={"state": "unknown-state", "code": "abc"},
    )
    assert response.status_code == 400
    assert "Invalid or expired OAuth state" in response.json()["detail"]


@pytest.mark.asyncio
async def test_spotify_callback_with_provider_error_redirects(client):
    state = "state-provider-error"
    spotify_auth._pending_states[state] = {
        "user_id": str(uuid.uuid4()),
        "return_to": "http://localhost/create",
    }

    response = await client.get(
        "/auth/spotify/callback",
        params={"state": state, "error": "access_denied"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "http://localhost/create?spotify_error=access_denied"
    )
    assert state not in spotify_auth._pending_states


@pytest.mark.asyncio
async def test_spotify_callback_token_exchange_failure_redirects(
    client, db_session, monkeypatch
):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()

    state = "state-token-fail"
    spotify_auth._pending_states[state] = {
        "user_id": user_id,
        "return_to": "http://localhost/create",
    }

    _SequencedAsyncClient.post_responses = [_FakeResponse({}, status_code=400)]
    monkeypatch.setattr(
        "api.routers.spotify_auth.httpx.AsyncClient", _SequencedAsyncClient
    )

    response = await client.get(
        "/auth/spotify/callback",
        params={"state": state, "code": "bad-code"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "http://localhost/create?spotify_error=token_exchange_failed"
    )


@pytest.mark.asyncio
async def test_spotify_callback_profile_fetch_failure_redirects(
    client, db_session, monkeypatch
):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()

    state = "state-profile-fail"
    spotify_auth._pending_states[state] = {
        "user_id": user_id,
        "return_to": "http://localhost/create",
    }

    _SequencedAsyncClient.post_responses = [
        _FakeResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
            },
            status_code=200,
        )
    ]
    _SequencedAsyncClient.get_responses = [_FakeResponse({}, status_code=401)]
    monkeypatch.setattr(
        "api.routers.spotify_auth.httpx.AsyncClient", _SequencedAsyncClient
    )

    response = await client.get(
        "/auth/spotify/callback",
        params={"state": state, "code": "ok-code"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert (
        response.headers["location"]
        == "http://localhost/create?spotify_error=profile_fetch_failed"
    )


@pytest.mark.asyncio
async def test_spotify_callback_success_stores_tokens_and_redirects(
    client, db_session, monkeypatch
):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()

    state = "state-success"
    spotify_auth._pending_states[state] = {
        "user_id": user_id,
        "return_to": "http://localhost/create",
    }

    _SequencedAsyncClient.post_responses = [
        _FakeResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 3600,
            }
        )
    ]
    _SequencedAsyncClient.get_responses = [_FakeResponse({"id": "spotify-external-id"})]
    monkeypatch.setattr(
        "api.routers.spotify_auth.httpx.AsyncClient", _SequencedAsyncClient
    )

    response = await client.get(
        "/auth/spotify/callback",
        params={"state": state, "code": "ok-code"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost/create?spotify_linked=true"

    provider_account = await crud.get_provider_account_by_user(user_id, "spotify")
    assert provider_account is not None
    assert provider_account.externalUserId == "spotify-external-id"
    assert provider_account.accessToken == "access-token"
    assert provider_account.refreshToken == "refresh-token"


@pytest.mark.asyncio
async def test_spotify_token_without_linked_account_returns_404(client):
    response = await client.get(
        "/auth/spotify/token",
        params={"user_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
    assert "No linked Spotify account" in response.json()["detail"]


@pytest.mark.asyncio
async def test_spotify_token_returns_cached_valid_access_token(client, db_session):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()
    await crud.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id="spotify-external-id",
        access_token="cached-access-token",
        refresh_token="refresh-token",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    response = await client.get("/auth/spotify/token", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json() == {"access_token": "cached-access-token"}


@pytest.mark.asyncio
async def test_spotify_token_refresh_success_updates_tokens(
    client, db_session, monkeypatch
):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()
    await crud.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id="spotify-external-id",
        access_token="expired-access-token",
        refresh_token="old-refresh-token",
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    _SequencedAsyncClient.post_responses = [
        _FakeResponse(
            {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }
        )
    ]
    monkeypatch.setattr(
        "api.routers.spotify_auth.httpx.AsyncClient", _SequencedAsyncClient
    )

    response = await client.get("/auth/spotify/token", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json() == {"access_token": "new-access-token"}

    provider_account = await crud.get_provider_account_by_user(user_id, "spotify")
    assert provider_account is not None
    assert provider_account.accessToken == "new-access-token"
    assert provider_account.refreshToken == "new-refresh-token"


@pytest.mark.asyncio
async def test_spotify_token_refresh_failure_returns_502(
    client, db_session, monkeypatch
):
    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "Host User", db_session)
    await crud.create_music_provider("spotify", "Spotify", db_session)
    await db_session.commit()
    await crud.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id="spotify-external-id",
        access_token="expired-access-token",
        refresh_token="old-refresh-token",
        token_expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    _SequencedAsyncClient.post_responses = [_FakeResponse({}, status_code=500)]
    monkeypatch.setattr(
        "api.routers.spotify_auth.httpx.AsyncClient", _SequencedAsyncClient
    )

    response = await client.get("/auth/spotify/token", params={"user_id": user_id})

    assert response.status_code == 502
    assert "Failed to refresh Spotify token" in response.json()["detail"]
