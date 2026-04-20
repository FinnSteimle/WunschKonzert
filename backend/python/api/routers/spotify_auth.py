from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

import repositories.crud as crud
import services.room_service as room_service
from services.providers import spotify_oauth

router = APIRouter()


@router.get("/auth/spotify/login")
async def spotify_login(user_id: str, return_to: str) -> dict[str, str]:
    """Return the Spotify authorize URL the frontend should redirect to."""
    await room_service.ensure_user_display_name(user_id, user_id)
    auth_url = await spotify_oauth.create_authorize_url(user_id, return_to)
    return {"auth_url": auth_url}


@router.get("/auth/spotify/callback")
async def spotify_callback(
    code: str = "", state: str = "", error: str = ""
) -> RedirectResponse:
    """Spotify redirects here after the user grants/denies access."""
    pending = await spotify_oauth.validate_callback_state(state)
    return_to = pending["return_to"]

    if error:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{sep}spotify_error={error}")

    user_id = pending["user_id"]
    try:
        token_data = await spotify_oauth.exchange_authorization_code(code)
    except spotify_oauth.SpotifyOAuthError as exc:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{sep}spotify_error={exc.code}")
    try:
        external_user_id = await spotify_oauth.fetch_profile_user_id(
            access_token=token_data.access_token, token_type=token_data.token_type
        )
    except spotify_oauth.SpotifyOAuthError as exc:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{sep}spotify_error={exc.code}")

    await crud.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id=external_user_id,
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        token_expires_at=token_data.token_expires_at,
    )

    sep = "&" if "?" in return_to else "?"
    return RedirectResponse(f"{return_to}{sep}spotify_linked=true")


@router.get("/auth/spotify/token")
async def spotify_token(user_id: str) -> dict[str, str]:
    """Return a fresh Spotify access token for the Web Playback SDK."""
    pa = await crud.get_provider_account_by_user(user_id, "spotify")
    if not pa or not pa.refreshToken:
        raise HTTPException(
            status_code=404,
            detail="No linked Spotify account found for this user",
        )

    # If the token is still valid, return it directly.
    if pa.accessToken and pa.tokenExpiresAt and datetime.now(UTC) < pa.tokenExpiresAt:
        return {"access_token": pa.accessToken}

    # Token expired -- refresh it.
    client_id, client_secret = spotify_oauth.spotify_credentials()
    auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_value}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": pa.refreshToken,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502, detail="Failed to refresh Spotify token"
            )
        token_data = resp.json()

    new_access = token_data["access_token"]
    new_refresh = token_data.get("refresh_token", pa.refreshToken)
    expires_in = int(token_data.get("expires_in", 3600))
    new_expires = datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60))

    await crud.update_provider_account_tokens(
        pa.providerAccountId,
        access_token=new_access,
        token_expires_at=new_expires,
        refresh_token=new_refresh if new_refresh != pa.refreshToken else None,
    )

    return {"access_token": new_access}
