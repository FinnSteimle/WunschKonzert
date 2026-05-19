from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import repositories.music_provider_repo as music_provider_repo
import repositories.user_repo as user_repo
import services.room_service as room_service
from core.exceptions import ResourceNotFoundError
from models.domain import AccountStatus
from services.providers.apple_music_jwt import get_developer_token

router = APIRouter()


class LinkRequest(BaseModel):
    user_id: str
    music_user_token: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


def _apple_api_url() -> str:
    return os.getenv("APPLE_MUSIC_API_URL", "https://api.music.apple.com")


@router.get("/auth/apple-music/developer-token")
async def apple_music_developer_token(user_id: str) -> dict[str, str]:
    await room_service.ensure_user_display_name(user_id, user_id)
    token = await get_developer_token()
    return {"developer_token": token}


@router.post("/auth/apple-music/link")
async def apple_music_link(body: LinkRequest) -> dict[str, str | None]:
    await room_service.ensure_user_display_name(body.user_id, body.display_name)

    dev_token = await get_developer_token()

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{_apple_api_url()}/v1/me/storefront",
            headers={
                "Authorization": f"Bearer {dev_token}",
                "Music-User-Token": body.music_user_token,
            },
        )

    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail={"code": "subscription_error"},
        )
    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_music_user_token"},
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request"},
        )

    data = response.json().get("data", [])
    storefront: str = data[0].get("id", "") if data else ""

    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=body.user_id,
        provider_id="apple-music",
        external_user_id=body.user_id,
        access_token=body.music_user_token,
        refresh_token=None,
        token_expires_at=None,
        storefront=storefront,
    )

    return {"storefront": storefront, "display_name": body.display_name}


@router.get("/auth/apple-music/token")
async def apple_music_token(user_id: str) -> dict[str, str]:
    pa = await music_provider_repo.get_provider_account_by_user(user_id, "apple-music")
    if pa is None or not pa.accessToken:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_linked"},
        )
    if pa.status == AccountStatus.SUSPENDED:
        raise HTTPException(
            status_code=409,
            detail={"code": "needs_relink"},
        )
    return {"music_user_token": pa.accessToken}


@router.get("/auth/apple-music/profile")
async def apple_music_profile(user_id: str) -> dict[str, object]:
    pa = await music_provider_repo.get_provider_account_by_user(user_id, "apple-music")
    if pa is None:
        return {
            "linked": False,
            "storefront": None,
            "display_name": None,
            "needs_relink": False,
        }

    display_name: str | None = None
    try:
        user = await user_repo.get_user(user_id)
        display_name = user.displayName
    except ResourceNotFoundError:
        pass

    needs_relink = pa.status == AccountStatus.SUSPENDED
    return {
        "linked": True,
        "storefront": pa.storefront,
        "display_name": display_name,
        "needs_relink": needs_relink,
    }
