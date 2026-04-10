import base64
import os
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Query

import repositories.crud as crud

router = APIRouter()

spotify_token_cache: dict[str, str | datetime | None] = {
    "token": None,
    "expires_at": None,
}


async def _get_spotify_access_token() -> str:
    cached_token = spotify_token_cache.get("token")
    cached_expiry = spotify_token_cache.get("expires_at")
    if isinstance(cached_token, str) and isinstance(cached_expiry, datetime):
        if datetime.now(UTC) < cached_expiry:
            return cached_token

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials are not configured on the backend",
        )

    auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_value}"},
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise HTTPException(
                status_code=502, detail="Spotify token response invalid"
            )
        spotify_token_cache["token"] = token
        spotify_token_cache["expires_at"] = datetime.now(UTC).replace(
            microsecond=0
        ) + timedelta(seconds=max(60, expires_in - 60))
        return token


@router.get("/rooms/{room_id}/search")
async def search_tracks(
    room_id: str, q: str = Query(..., min_length=1, max_length=120)
):
    room = await crud.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if (
        room.status.value != "active"
        if hasattr(room.status, "value")
        else room.status != "active"
    ):
        # Handle enum vs string
        pass

    # Using crud might return enum, let's just check the property
    from models.domain import RoomStatus

    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    if str(room.supportedProviderId).lower() != "spotify":
        raise HTTPException(status_code=400, detail="Only spotify is supported in MVP")

    token = await _get_spotify_access_token()
    spotify_market = os.getenv("SPOTIFY_MARKET", "CH")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.spotify.com/v1/search",
            params={"q": q, "type": "track", "limit": 10, "market": spotify_market},
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Spotify search failed: {detail}",
            ) from exc
        payload = response.json()

    items = payload.get("tracks", {}).get("items", [])
    tracks = []
    for item in items:
        album = item.get("album") or {}
        images = album.get("images") or []
        artists = item.get("artists") or []
        tracks.append(
            {
                "trackId": item.get("id"),
                "providerTrackId": item.get("id"),
                "title": item.get("name") or "Unknown title",
                "artist": ", ".join(
                    artist.get("name", "") for artist in artists if artist.get("name")
                )
                or "Unknown artist",
                "album": album.get("name") or "",
                "duration": int((item.get("duration_ms") or 0) / 1000),
                "coverUrl": images[0].get("url") if images else "",
                "deepLink": item.get("external_urls", {}).get("spotify", ""),
            }
        )

    return {"provider": "spotify", "query": q, "tracks": tracks}
