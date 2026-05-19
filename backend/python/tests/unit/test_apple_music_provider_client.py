from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from services.providers.apple_music_client import AppleMusicProviderClient

pytestmark = pytest.mark.unit


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
            detail = (
                self.payload.get("detail") if isinstance(self.payload, dict) else None
            )
            raise HTTPException(status_code=self.status_code, detail=detail)


@pytest.mark.asyncio
async def test_apple_music_client_maps_tracks(monkeypatch):
    """Test that Apple Music client correctly maps API response to ProviderTrack."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    # Mock developer token response
    search_response = _FakeResponse(
        {
            "results": {
                "songs": {
                    "data": [
                        {
                            "id": "song1",
                            "attributes": {
                                "name": "Fire",
                                "artistName": "Artist1",
                                "albumName": "Album1",
                                "durationInMillis": 180000,
                                "artwork": {
                                    "url": "https://example.com/image/{w}x{h}.jpg"
                                },
                                "url": "https://music.apple.com/song1",
                            },
                        }
                    ]
                }
            }
        }
    )

    async def mock_get(*args, **kwargs):
        return search_response

    # Mock the provider account lookup and JWT signer
    mock_get_account = AsyncMock()
    mock_get_account.return_value.storefront = "us"

    mock_get_token = AsyncMock()
    mock_get_token.return_value = "dev-token"

    with (
        patch(
            "services.providers.apple_music_client.httpx.AsyncClient.get",
            side_effect=mock_get,
        ),
        patch(
            "services.providers.apple_music_client.music_provider_repo.get_provider_account_by_user",
            side_effect=mock_get_account,
        ),
        patch(
            "services.providers.apple_music_client.get_developer_token",
            side_effect=mock_get_token,
        ),
    ):
        client = AppleMusicProviderClient()
        tracks = await client.search_tracks("fire", user_id="user1")

        assert len(tracks) == 1
        assert tracks[0].title == "Fire"
        assert tracks[0].artist == "Artist1"
        assert tracks[0].album == "Album1"
        assert tracks[0].duration == 180
        assert "640x640" in tracks[0].cover_url
        assert tracks[0].deep_link == "https://music.apple.com/song1"


@pytest.mark.asyncio
async def test_apple_music_client_find_track_for_user_exact_match(monkeypatch):
    """Test that find_track_for_user returns exact title/artist match."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    search_response = _FakeResponse(
        {
            "results": {
                "songs": {
                    "data": [
                        {
                            "id": "song1",
                            "attributes": {
                                "name": "Fire",
                                "artistName": "Artist1",
                                "albumName": "Album1",
                                "durationInMillis": 180000,
                                "artwork": {
                                    "url": "https://example.com/image/{w}x{h}.jpg"
                                },
                                "url": "https://music.apple.com/song1",
                            },
                        },
                        {
                            "id": "song2",
                            "attributes": {
                                "name": "Fire (Remix)",
                                "artistName": "Artist1",
                                "albumName": "Album2",
                                "durationInMillis": 200000,
                                "artwork": {
                                    "url": "https://example.com/image/{w}x{h}.jpg"
                                },
                                "url": "https://music.apple.com/song2",
                            },
                        },
                    ]
                }
            }
        }
    )

    async def mock_get(*args, **kwargs):
        return search_response

    mock_get_account = AsyncMock()
    mock_get_account.return_value.storefront = "us"

    mock_get_token = AsyncMock()
    mock_get_token.return_value = "dev-token"

    with (
        patch(
            "services.providers.apple_music_client.httpx.AsyncClient.get",
            side_effect=mock_get,
        ),
        patch(
            "services.providers.apple_music_client.music_provider_repo.get_provider_account_by_user",
            side_effect=mock_get_account,
        ),
        patch(
            "services.providers.apple_music_client.get_developer_token",
            side_effect=mock_get_token,
        ),
    ):
        client = AppleMusicProviderClient()
        track = await client.find_track_for_user(
            user_id="user1", title="Fire", artist="Artist1"
        )

        assert track is not None
        assert track.title == "Fire"
        assert track.album == "Album1"


@pytest.mark.asyncio
async def test_apple_music_client_find_track_for_user_no_match(monkeypatch):
    """Test that find_track_for_user returns None when no match found."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    search_response = _FakeResponse({"results": {"songs": {"data": []}}})

    async def mock_get(*args, **kwargs):
        return search_response

    mock_get_account = AsyncMock()
    mock_get_account.return_value.storefront = "us"

    mock_get_token = AsyncMock()
    mock_get_token.return_value = "dev-token"

    with (
        patch(
            "services.providers.apple_music_client.httpx.AsyncClient.get",
            side_effect=mock_get,
        ),
        patch(
            "services.providers.apple_music_client.music_provider_repo.get_provider_account_by_user",
            side_effect=mock_get_account,
        ),
        patch(
            "services.providers.apple_music_client.get_developer_token",
            side_effect=mock_get_token,
        ),
    ):
        client = AppleMusicProviderClient()
        track = await client.find_track_for_user(
            user_id="user1", title="NonExistent", artist="Unknown"
        )

        assert track is None


@pytest.mark.asyncio
async def test_apple_music_client_missing_storefront_raises_400(monkeypatch):
    """Test that missing storefront raises HTTPException 400."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    mock_get_account = AsyncMock()
    mock_get_account.return_value.storefront = None

    mock_get_token = AsyncMock()
    mock_get_token.return_value = "dev-token"

    with (
        patch(
            "services.providers.apple_music_client.music_provider_repo.get_provider_account_by_user",
            side_effect=mock_get_account,
        ),
        patch(
            "services.providers.apple_music_client.get_developer_token",
            side_effect=mock_get_token,
        ),
    ):
        client = AppleMusicProviderClient()
        with pytest.raises(HTTPException) as exc_info:
            await client.search_tracks("fire", user_id="user1")
        assert exc_info.value.status_code == 400
        assert "storefront not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_apple_music_client_api_error_raises_exception(monkeypatch):
    """Test that API errors are properly raised."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    error_response = _FakeResponse({"error": "Unauthorized"}, status_code=401)

    async def mock_get(*args, **kwargs):
        return error_response

    mock_get_account = AsyncMock()
    mock_get_account.return_value.storefront = "us"

    mock_get_token = AsyncMock()
    mock_get_token.return_value = "dev-token"

    with (
        patch(
            "services.providers.apple_music_client.httpx.AsyncClient.get",
            side_effect=mock_get,
        ),
        patch(
            "services.providers.apple_music_client.music_provider_repo.get_provider_account_by_user",
            side_effect=mock_get_account,
        ),
        patch(
            "services.providers.apple_music_client.get_developer_token",
            side_effect=mock_get_token,
        ),
    ):
        client = AppleMusicProviderClient()
        with pytest.raises(HTTPException) as exc_info:
            await client.search_tracks("fire", user_id="user1")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_apple_music_client_is_linked(monkeypatch):
    """Test is_linked method."""
    monkeypatch.setenv("APPLE_MUSIC_TEAM_ID", "team-id")
    monkeypatch.setenv("APPLE_MUSIC_KEY_ID", "key-id")
    monkeypatch.setenv(
        "APPLE_MUSIC_PRIVATE_KEY",
        "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIIGlVmKjgvwv5Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8Yd8oAoGCCqGSM49\nAwEHoUQDQgAE1234567890123456789012345678901234567890123456789012\n-----END EC PRIVATE KEY-----",
    )

    from models.domain import ProviderAccount

    client = AppleMusicProviderClient()

    # Mock account with accessToken
    account_with_token = AsyncMock(spec=ProviderAccount)
    account_with_token.accessToken = "mut-token"
    assert client.is_linked(account_with_token) is True

    # Mock account without accessToken
    account_without_token = AsyncMock(spec=ProviderAccount)
    account_without_token.accessToken = None
    assert client.is_linked(account_without_token) is False
