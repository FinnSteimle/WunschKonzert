from __future__ import annotations

import os

import httpx
from fastapi import HTTPException

import repositories.music_provider_repo as music_provider_repo
from models.domain import ProviderAccount
from services.providers.apple_music_jwt import get_developer_token
from services.providers.base import ProviderTrack

APPLE_MUSIC_ARTWORK_SIZE = 640


class AppleMusicProviderClient:
    provider_id = "apple-music"

    def _api_url(self) -> str:
        return os.getenv("APPLE_MUSIC_API_URL", "https://api.music.apple.com")

    async def _resolve_storefront(self, user_id: str) -> str:
        pa = await music_provider_repo.get_provider_account_by_user(
            user_id, "apple-music"
        )
        if pa and pa.storefront:
            return pa.storefront
        raise HTTPException(
            status_code=400,
            detail="User's Apple Music account storefront not found. Please re-link your account.",
        )

    async def _catalog_search(self, query: str, storefront: str) -> list[ProviderTrack]:
        # Catalog search uses the developer token only (MUT not required).
        token = await get_developer_token()
        url = f"{self._api_url()}/v1/catalog/{storefront}/search"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                url,
                params={"term": query, "types": "songs", "limit": 20},
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=f"Apple Music search failed: {response.text}",
                ) from exc
            payload = response.json()

        songs = payload.get("results", {}).get("songs", {}).get("data", [])
        return [self._to_track(item) for item in songs]

    async def search_tracks(self, query: str, user_id: str) -> list[ProviderTrack]:
        storefront = await self._resolve_storefront(user_id)
        return await self._catalog_search(query, storefront)

    async def find_track_for_user(
        self, *, user_id: str, title: str, artist: str
    ) -> ProviderTrack | None:
        storefront = await self._resolve_storefront(user_id)
        tracks = await self._catalog_search(f"{title} {artist}", storefront)

        target_title = title.strip().casefold()
        target_artist = artist.strip().casefold()

        best: ProviderTrack | None = None
        for track in tracks:
            cand_title = track.title.strip().casefold()
            cand_artist = track.artist.strip().casefold()
            if cand_title == target_title and target_artist in cand_artist:
                return track
            if best is None and target_artist in cand_artist:
                best = track
        return best

    def is_linked(self, account: ProviderAccount) -> bool:
        return bool(account.accessToken)

    def _to_track(self, item: dict[str, object]) -> ProviderTrack:
        track_id_raw = item.get("id")
        track_id = track_id_raw if isinstance(track_id_raw, str) else ""

        attrs = item.get("attributes")
        attrs_data = attrs if isinstance(attrs, dict) else {}

        name_raw = attrs_data.get("name")
        title = name_raw if isinstance(name_raw, str) else "Unknown title"

        artist_raw = attrs_data.get("artistName")
        artist = artist_raw if isinstance(artist_raw, str) else "Unknown artist"

        album_raw = attrs_data.get("albumName")
        album = album_raw if isinstance(album_raw, str) else ""

        duration_ms = attrs_data.get("durationInMillis")
        duration = int(duration_ms / 1000) if isinstance(duration_ms, int) else 0

        artwork = attrs_data.get("artwork")
        artwork_data = artwork if isinstance(artwork, dict) else {}
        artwork_url_raw = artwork_data.get("url")
        if isinstance(artwork_url_raw, str):
            size = str(APPLE_MUSIC_ARTWORK_SIZE)
            cover_url = artwork_url_raw.replace("{w}", size).replace("{h}", size)
        else:
            cover_url = ""

        deep_link_raw = attrs_data.get("url")
        deep_link = deep_link_raw if isinstance(deep_link_raw, str) else ""

        return ProviderTrack(
            track_id=track_id,
            provider_track_id=track_id,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_url=cover_url,
            deep_link=deep_link,
        )
