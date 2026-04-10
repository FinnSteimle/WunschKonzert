import pytest
from fastapi import HTTPException

from services.providers.spotify_client import SpotifyProviderClient


class _FakeResponse:
    def __init__(
        self,
        payload: dict,
        status_code: int = 200,
        text: str = "",
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("status error")


class _FakeAsyncClient:
    post_calls = 0
    get_calls = 0

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, data: dict) -> _FakeResponse:
        _FakeAsyncClient.post_calls += 1
        return _FakeResponse({"access_token": "token-123", "expires_in": 3600})

    async def get(self, url: str, params: dict, headers: dict) -> _FakeResponse:
        _FakeAsyncClient.get_calls += 1
        return _FakeResponse(
            {
                "tracks": {
                    "items": [
                        {
                            "id": "abc123",
                            "name": "Firework",
                            "duration_ms": 228000,
                            "album": {
                                "name": "Teenage Dream",
                                "images": [{"url": "https://cover"}],
                            },
                            "artists": [{"name": "Katy Perry"}],
                            "external_urls": {"spotify": "https://open.spotify.com/track/abc123"},
                        }
                    ]
                }
            }
        )


@pytest.mark.asyncio
async def test_spotify_client_maps_tracks_and_reuses_cached_token(monkeypatch):
    _FakeAsyncClient.post_calls = 0
    _FakeAsyncClient.get_calls = 0
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(
        "services.providers.spotify_client.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    client = SpotifyProviderClient()
    first = await client.search_tracks("fire")
    second = await client.search_tracks("fire again")

    assert len(first) == 1
    assert first[0].track_id == "abc123"
    assert first[0].provider_track_id == "abc123"
    assert first[0].title == "Firework"
    assert first[0].artist == "Katy Perry"
    assert first[0].album == "Teenage Dream"
    assert first[0].duration == 228
    assert first[0].cover_url == "https://cover"
    assert first[0].deep_link == "https://open.spotify.com/track/abc123"
    assert len(second) == 1
    assert _FakeAsyncClient.post_calls == 1
    assert _FakeAsyncClient.get_calls == 2


@pytest.mark.asyncio
async def test_spotify_client_missing_credentials_raises_503(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    client = SpotifyProviderClient()

    with pytest.raises(HTTPException) as exc_info:
        await client.search_tracks("anything")

    assert exc_info.value.status_code == 503
    assert "Spotify credentials are not configured" in exc_info.value.detail
