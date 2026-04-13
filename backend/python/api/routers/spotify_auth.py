from __future__ import annotations

import base64
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

import repositories.crud as crud
import services.room_service as room_service

router = APIRouter()

SPOTIFY_SCOPES = " ".join(
    [
        "streaming",
        "user-read-email",
        "user-read-private",
        "user-modify-playback-state",
        "user-read-playback-state",
    ]
)

# In-memory store for OAuth state tokens.
# Maps state -> {user_id, return_to, created_at}
_pending_states: dict[str, dict[str, str]] = {}


def _spotify_credentials() -> tuple[str, str]:
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials are not configured on the backend",
        )
    return client_id, client_secret


def _redirect_uri() -> str:
    uri = os.getenv("SPOTIFY_REDIRECT_URI", "")
    if not uri:
        raise HTTPException(
            status_code=503, detail="SPOTIFY_REDIRECT_URI is not configured"
        )
    return uri


@router.get("/auth/spotify/login")
async def spotify_login(user_id: str, return_to: str) -> dict[str, str]:
    """Return the Spotify authorize URL the frontend should redirect to."""
    await room_service.ensure_user_display_name(user_id, user_id)

    client_id, _ = _spotify_credentials()
    redirect_uri = _redirect_uri()

    state = secrets.token_urlsafe(32)
    _pending_states[state] = {
        "user_id": user_id,
        "return_to": return_to,
    }

    params = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": SPOTIFY_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return {"auth_url": f"https://accounts.spotify.com/authorize?{params}"}


@router.get("/auth/spotify/callback")
async def spotify_callback(
    code: str = "", state: str = "", error: str = ""
) -> RedirectResponse:
    """Spotify redirects here after the user grants/denies access."""
    pending = _pending_states.pop(state, None)
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    return_to: str = pending["return_to"]

    if error:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{sep}spotify_error={error}")

    user_id: str = pending["user_id"]
    client_id, client_secret = _spotify_credentials()
    redirect_uri = _redirect_uri()

    auth_value = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_value}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code != 200:
            sep = "&" if "?" in return_to else "?"
            return RedirectResponse(
                f"{return_to}{sep}spotify_error=token_exchange_failed"
            )
        token_data = resp.json()

    access_token: str = token_data["access_token"]
    refresh_token: str = token_data["refresh_token"]
    expires_in: int = int(token_data.get("expires_in", 3600))
    token_expires_at = datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60))

    # Fetch the Spotify user profile to get the external user id.
    async with httpx.AsyncClient(timeout=10) as http:
        profile_resp = await http.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code != 200:
            sep = "&" if "?" in return_to else "?"
            return RedirectResponse(
                f"{return_to}{sep}spotify_error=profile_fetch_failed"
            )
        profile = profile_resp.json()

    external_user_id: str = profile.get("id", "unknown")

    await crud.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id=external_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
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
    if (
        pa.accessToken
        and pa.tokenExpiresAt
        and datetime.now(UTC) < pa.tokenExpiresAt
    ):
        return {"access_token": pa.accessToken}

    # Token expired -- refresh it.
    client_id, client_secret = _spotify_credentials()
    auth_value = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

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
