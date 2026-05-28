from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

import repositories.music_provider_repo as music_provider_repo
from services.providers import spotify_oauth

router = APIRouter()


@router.get("/auth/spotify/login")
async def spotify_login(
    user_id: str, return_to: str, force_consent: bool = False
) -> dict[str, str]:
    """Return the Spotify authorize URL the frontend should redirect to."""
    auth_url = await spotify_oauth.create_authorize_url(
        user_id, return_to, prompt_consent=force_consent
    )
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
        profile = await spotify_oauth.fetch_spotify_profile(
            access_token=token_data.access_token, token_type=token_data.token_type
        )
    except spotify_oauth.SpotifyOAuthError as exc:
        sep = "&" if "?" in return_to else "?"
        return RedirectResponse(f"{return_to}{sep}spotify_error={exc.code}")

    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id="spotify",
        external_user_id=profile.user_id,
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        token_expires_at=token_data.token_expires_at,
        storefront=profile.country,
    )

    sep = "&" if "?" in return_to else "?"
    return RedirectResponse(f"{return_to}{sep}spotify_linked=true")


@router.get("/auth/spotify/token")
async def spotify_token(user_id: str) -> dict[str, str]:
    """Return a fresh Spotify access token for the Web Playback SDK."""
    access_token = await spotify_oauth.get_user_access_token(user_id)
    return {"access_token": access_token}
