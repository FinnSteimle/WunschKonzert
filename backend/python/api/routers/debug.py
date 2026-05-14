from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import repositories.music_provider_repo as music_provider_repo
import repositories.user_repo as user_repo
from core.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/debug", tags=["debug"])


class SeedUserRequest(BaseModel):
    user_id: str
    display_name: str


@router.post("/seed_user")
async def seed_user(data: SeedUserRequest) -> dict[str, object]:
    """
    Seeds a user with a linked Spotify account for load testing.
    Available in development and staging environments.
    """
    try:
        # 1. Ensure user exists
        try:
            await user_repo.get_user(data.user_id)
        except ResourceNotFoundError:
            await user_repo.create_user(data.user_id, data.display_name)

        # 2. Link a dummy Spotify account so create_room_service passes
        await music_provider_repo.create_or_update_provider_account_tokens(
            user_id=data.user_id,
            provider_id="spotify",
            external_user_id=f"ext-{data.user_id}",
            access_token="mock-access-token",
            refresh_token="mock-refresh-token",
            token_expires_at=datetime.now(UTC) + timedelta(days=1),
        )

        return {
            "success": True,
            "message": f"User {data.user_id} seeded with mock Spotify tokens",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
