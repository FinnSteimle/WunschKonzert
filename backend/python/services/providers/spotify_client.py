from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException

from services.providers.base import ProviderTrack


class SpotifyProviderClient:
    provider_id = "spotify"

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: datetime | None = None

    async def _get_access_token(self) -> str:
        if self._token and self._expires_at and datetime.now(UTC) < self._expires_at:
            return self._token

        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise HTTPException(
                status_code=503,
                detail="Spotify credentials are not configured on the backend",
            )

        auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        token_url = os.getenv(
            "SPOTIFY_TOKEN_URL", "https://accounts.spotify.com/api/token"
        )

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                token_url,
                headers={"Authorization": f"Basic {auth_value}"},
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            payload = response.json()

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not isinstance(token, str) or not token:
            raise HTTPException(
                status_code=502, detail="Spotify token response invalid"
            )

        self._token = token
        self._expires_at = datetime.now(UTC).replace(microsecond=0) + timedelta(
            seconds=max(60, expires_in - 60)
        )
        return token

    async def search_tracks(self, query: str) -> list[ProviderTrack]:
        token = await self._get_access_token()
        spotify_market = os.getenv("SPOTIFY_MARKET", "CH")
        search_url = os.getenv(
            "SPOTIFY_SEARCH_URL", "https://api.spotify.com/v1/search"
        )

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                search_url,
                params={
                    "q": query,
                    "type": "track",
                    "limit": 10,
                    "market": spotify_market,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=f"Spotify search failed: {response.text}",
                ) from exc
            payload = response.json()

        return [
            self._to_track(item) for item in payload.get("tracks", {}).get("items", [])
        ]

    def _to_track(self, item: dict[str, object]) -> ProviderTrack:
        track_id_raw = item.get("id")
        track_id = (
            track_id_raw if isinstance(track_id_raw, str) and track_id_raw else ""
        )

        album = item.get("album")
        album_data = album if isinstance(album, dict) else {}
        album_name_raw = album_data.get("name")
        album_name = album_name_raw if isinstance(album_name_raw, str) else ""

        artists_value = item.get("artists")
        artists = artists_value if isinstance(artists_value, list) else []
        artist_names = []
        for artist in artists:
            if isinstance(artist, dict):
                artist_name = artist.get("name")
                if isinstance(artist_name, str) and artist_name:
                    artist_names.append(artist_name)

        images_value = album_data.get("images")
        images = images_value if isinstance(images_value, list) else []
        cover_url = ""
        if images and isinstance(images[0], dict):
            first_url = images[0].get("url")
            if isinstance(first_url, str):
                cover_url = first_url

        external_urls = item.get("external_urls")
        external_data = external_urls if isinstance(external_urls, dict) else {}
        spotify_link = external_data.get("spotify")
        deep_link = spotify_link if isinstance(spotify_link, str) else ""

        duration_ms = item.get("duration_ms")
        duration = int(duration_ms / 1000) if isinstance(duration_ms, int) else 0

        title_raw = item.get("name")
        title = (
            title_raw if isinstance(title_raw, str) and title_raw else "Unknown title"
        )

        return ProviderTrack(
            track_id=track_id,
            provider_track_id=track_id,
            title=title,
            artist=", ".join(artist_names) if artist_names else "Unknown artist",
            album=album_name,
            duration=duration,
            cover_url=cover_url,
            deep_link=deep_link,
        )
