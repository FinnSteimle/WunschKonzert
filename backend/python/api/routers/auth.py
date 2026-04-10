from fastapi import APIRouter, HTTPException

import repositories.crud as crud
from models.schemas import (
    AddMusicProviderRequest,
    AddMusicProviderResponse,
    AuthRequest,
    AuthResponse,
)

router = APIRouter()


@router.post("/auth/account", response_model=AuthResponse)
async def auth_account(auth_data: AuthRequest):
    return {
        "success": True,
        "message": "Account authentication successful",
        "token": "dummy_account_token_12345",
    }


@router.post("/add_music_provider", response_model=AddMusicProviderResponse)
async def add_music_provider(provider_data: AddMusicProviderRequest):
    user = await crud.get_user(provider_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        provider_account = await crud.create_provider_account(
            provider_data.user_id,
            provider_data.provider_id,
            provider_data.external_user_id,
        )
        return {
            "success": True,
            "message": f"Successfully linked provider {provider_data.provider_id} to user",
            "provider_account_id": provider_account.providerAccountId,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to add music provider: {str(e)}"
        )
