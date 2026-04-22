import pytest
from unittest.mock import patch
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from services.providers.spotify_client import SpotifyProviderClient


class _FakeResponse:
    def __init__(
        self, payload: dict[str, object] | None, status_code: int = 200
    ) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object] | None:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            detail = self.payload.get("detail") if isinstance(self.payload, dict) else None
            raise HTTPException(status_code=self.status_code, detail=detail)


@pytest.mark.asyncio
async def test_spotify_client_maps_tracks_and_reuses_cached_token(monkeypatch):
    # Setup environment
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "client-secret")

    # Mock token response
    token_response = _FakeResponse(
        {"access_token": "new-token", "expires_in": 3600, "token_type": "Bearer"}
    )

    # Mock track search response
    track_response = _FakeResponse(
        {
            "tracks": {
                "items": [
                    {
                        "id": "track1",
                        "name": "Fire",
                        "artists": [{"name": "Artist1"}],
                        "duration_ms": 120000,
                        "album": {"images": [{"url": "http://image.url"}]},
                        "uri": "spotify:track:track1",
                    }
                ]
            }
        }
    )

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return token_response

    async def mock_get(*args, **kwargs):
        return track_response

    with (
        patch(
            "services.providers.spotify_client.httpx.AsyncClient.post",
            side_effect=mock_post,
        ),
        patch(
            "services.providers.spotify_client.httpx.AsyncClient.get",
            side_effect=mock_get,
        ),
    ):
        client = SpotifyProviderClient()
        first = await client.search_tracks("fire")
        second = await client.search_tracks("fire again")

        assert len(first) == 1
        assert first[0].title == "Fire"
        assert len(second) == 1
        # Assert call_count is 1 because token should be cached
        assert call_count == 1


@pytest.mark.asyncio
async def test_spotify_client_missing_credentials_raises_503(monkeypatch):
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)

    client = SpotifyProviderClient()
    with pytest.raises(HTTPException) as exc_info:
        await client.search_tracks("anything")
    assert exc_info.value.status_code == 503
    assert "Spotify credentials are not configured" in exc_info.value.detail
