from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException

import repositories.music_provider_repo as music_provider_repo
from models.domain import ProviderAccount
from services.providers import spotify_oauth
from services.providers.base import ProviderTrack


class SpotifyProviderClient:
    provider_id: str = "spotify"

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

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    token_url,
                    headers={"Authorization": f"Basic {auth_value}"},
                    data={"grant_type": "client_credentials"},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Spotify is currently unavailable"
            ) from exc

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

    def is_linked(self, account: ProviderAccount) -> bool:
        return bool(account.refreshToken)

    async def _resolve_market(self, user_id: str) -> str:
        pa = await music_provider_repo.get_provider_account_by_user(user_id, "spotify")
        if pa and pa.storefront:
            return pa.storefront
        raise HTTPException(
            status_code=400,
            detail="User's Spotify account storefront not found. Please re-link your account.",
        )

    async def search_tracks(
        self, query: str, user_id: str | None = None
    ) -> list[ProviderTrack]:
        if user_id is None:
            raise HTTPException(
                status_code=400, detail="user_id is required for Spotify search"
            )
        token = await self._get_access_token()
        market = await self._resolve_market(user_id)
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
                    "market": market,
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

    async def find_track_for_user(
        self, *, user_id: str, title: str, artist: str
    ) -> ProviderTrack | None:
        """Search Spotify on behalf of the user and return the best Title+Artist match."""
        token = await spotify_oauth.get_user_access_token(user_id)
        market = await self._resolve_market(user_id)
        search_url = os.getenv(
            "SPOTIFY_SEARCH_URL", "https://api.spotify.com/v1/search"
        )

        query = f'track:"{title}" artist:"{artist}"'
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    search_url,
                    params={
                        "q": query,
                        "type": "track",
                        "limit": 5,
                        "market": market,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            return None
        payload = response.json()

        items = payload.get("tracks", {}).get("items", [])
        if not items:
            return None

        target_title = title.strip().casefold()
        target_artist = artist.strip().casefold()

        best: ProviderTrack | None = None
        for item in items:
            candidate = self._to_track(item)
            cand_title = candidate.title.strip().casefold()
            cand_artist = candidate.artist.strip().casefold()
            if cand_title == target_title and target_artist in cand_artist:
                return candidate
            if best is None and target_artist in cand_artist:
                best = candidate

        return best

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
