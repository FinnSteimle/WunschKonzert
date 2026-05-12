from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import HTTPException

import repositories.music_provider_repo as music_provider_repo
from services.providers import oauth_state

SPOTIFY_SCOPES = " ".join(
    [
        "streaming",
        "user-read-email",
        "user-read-private",
        "user-modify-playback-state",
        "user-read-playback-state",
    ]
)
STATE_TTL_SECONDS = 15 * 60


class SpotifyOAuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SpotifyOAuthTokens:
    access_token: str
    refresh_token: str
    token_type: str
    token_expires_at: datetime


def spotify_credentials() -> tuple[str, str]:
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials are not configured on the backend",
        )
    return client_id, client_secret


def spotify_redirect_uri() -> str:
    uri = os.getenv("SPOTIFY_REDIRECT_URI", "").strip()
    if uri.startswith("="):
        uri = uri.lstrip("=")
    if not uri:
        raise HTTPException(
            status_code=503, detail="SPOTIFY_REDIRECT_URI is not configured"
        )
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(
            status_code=503,
            detail="SPOTIFY_REDIRECT_URI must be an absolute URL",
        )
    return uri


def spotify_state_secret() -> str:
    secret = os.getenv("SPOTIFY_OAUTH_STATE_SECRET", "") or os.getenv(
        "SPOTIFY_CLIENT_SECRET", ""
    )
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Spotify credentials are not configured on the backend",
        )
    return secret


async def create_authorize_url(user_id: str, return_to: str) -> str:
    client_id, _ = spotify_credentials()
    redirect_uri = spotify_redirect_uri()
    state = await oauth_state.issue_state(
        provider_id="spotify",
        secret=spotify_state_secret(),
        user_id=user_id,
        return_to=return_to,
        ttl_seconds=STATE_TTL_SECONDS,
    )
    params = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "scope": SPOTIFY_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"https://accounts.spotify.com/authorize?{params}"


async def validate_callback_state(state: str) -> dict[str, str]:
    return await oauth_state.verify_and_consume_state(
        provider_id="spotify",
        secret=spotify_state_secret(),
        state=state,
        ttl_seconds=STATE_TTL_SECONDS,
    )


async def exchange_authorization_code(code: str) -> SpotifyOAuthTokens:
    client_id, client_secret = spotify_credentials()
    redirect_uri = spotify_redirect_uri()
    auth_value = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

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
            raise SpotifyOAuthError("token_exchange_failed")
        token_data = resp.json()

    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SpotifyOAuthError("token_exchange_failed")
    token_type = token_data.get("token_type", "Bearer")
    if not isinstance(token_type, str) or not token_type:
        token_type = "Bearer"
    refresh_token = token_data.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise SpotifyOAuthError("token_exchange_failed")

    expires_in = int(token_data.get("expires_in", 3600))
    token_expires_at = datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60))
    return SpotifyOAuthTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type=token_type,
        token_expires_at=token_expires_at,
    )


async def get_user_access_token(user_id: str) -> str:
    """Return a valid Spotify access token for the given user.

    Reuses the stored token while it is still valid, otherwise refreshes it
    using the stored refresh token and persists the new access token + expiry.
    """
    pa = await music_provider_repo.get_provider_account_by_user(user_id, "spotify")
    if not pa or not pa.refreshToken:
        raise HTTPException(
            status_code=404,
            detail="No linked Spotify account found for this user",
        )

    if pa.accessToken and pa.tokenExpiresAt and datetime.now(UTC) < pa.tokenExpiresAt:
        return pa.accessToken

    client_id, client_secret = spotify_credentials()
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
    if not isinstance(new_access, str) or not new_access:
        raise HTTPException(
            status_code=502, detail="Failed to refresh Spotify token"
        )
    new_refresh = token_data.get("refresh_token", pa.refreshToken)
    expires_in = int(token_data.get("expires_in", 3600))
    new_expires = datetime.now(UTC) + timedelta(seconds=max(60, expires_in - 60))

    await music_provider_repo.update_provider_account_tokens(
        pa.providerAccountId,
        access_token=new_access,
        token_expires_at=new_expires,
        refresh_token=new_refresh if new_refresh != pa.refreshToken else None,
    )

    return new_access


async def fetch_profile_user_id(access_token: str, token_type: str) -> str:
    async with httpx.AsyncClient(timeout=10) as http:
        profile_resp = await http.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"{token_type} {access_token}"},
        )
        if profile_resp.status_code != 200:
            raise SpotifyOAuthError("profile_fetch_failed")
        profile = profile_resp.json()

    external_user_id = profile.get("id")
    if not isinstance(external_user_id, str) or not external_user_id:
        return "unknown"
    return external_user_id
