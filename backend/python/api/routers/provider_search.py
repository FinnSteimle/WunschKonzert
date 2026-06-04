from fastapi import APIRouter, HTTPException, Query

import repositories.room_repo as room_repo
from models.domain import RoomStatus
from services.providers.registry import get_provider_client

router = APIRouter()


@router.get("/rooms/{room_id}/search")
async def search_tracks(
    room_id: str, q: str = Query(..., min_length=1, max_length=120)
) -> dict[str, object]:
    room = await room_repo.get_room(room_id)

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

    provider_id = str(room.supportedProviderId)
    provider = get_provider_client(provider_id)
    tracks = await provider.search_tracks(q, user_id=str(room.hostedBy))

    return {
        "provider": provider.provider_id,
        "query": q,
        "tracks": [track.to_api_dict() for track in tracks],
    }
