from fastapi import APIRouter

import api.websockets as websockets
import services.room_service as room_service
from models.schemas import (
    CreateRoomRequest,
    DeleteRoomRequest,
    LeaveRoomRequest,
    RoomAvailabilityRequest,
    RoomAvailabilityResponse,
    RoomRequest,
    RoomResponse,
)

router = APIRouter()


@router.post("/create_room", response_model=RoomResponse)
async def create_room_endpoint(room_data: CreateRoomRequest) -> dict[str, object]:
    return await room_service.create_room_service(
        room_data.name,
        room_data.user_id,
        room_data.display_name,
        room_data.supported_provider_id,
    )


@router.post("/join_room", response_model=RoomResponse)
async def join_room(room_data: RoomRequest) -> dict[str, object]:
    result = await room_service.join_room_service(
        room_data.join_code, room_data.user_id, room_data.display_name
    )
    # Notify other participants via websocket (refresh state since someone joined)
    await websockets.send_room_state(str(result["room_id"]), force_refresh=True)
    return result


@router.post("/leave_room", response_model=RoomResponse)
async def leave_room(room_data: LeaveRoomRequest) -> dict[str, object]:
    await room_service.leave_room_service(room_data.room_id, room_data.user_id)
    await websockets.send_room_state(room_data.room_id, force_refresh=True)
    return {
        "success": True,
        "message": f"Successfully left room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


@router.post("/delete_room", response_model=RoomResponse)
async def delete_room(room_data: DeleteRoomRequest) -> dict[str, object]:
    await room_service.delete_room_service(room_data.room_id, room_data.user_id)
    await websockets.send_room_state(room_data.room_id, force_refresh=True)
    return {
        "success": True,
        "message": f"Successfully deleted room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


@router.post("/rooms/availability", response_model=RoomAvailabilityResponse)
async def rooms_availability(
    payload: RoomAvailabilityRequest,
) -> RoomAvailabilityResponse:
    available, unavailable = await room_service.check_room_availability(
        payload.join_codes
    )
    return RoomAvailabilityResponse(
        available_join_codes=available,
        unavailable_join_codes=unavailable,
    )
