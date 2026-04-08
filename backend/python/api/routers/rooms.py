from fastapi import APIRouter, HTTPException

import api.websockets as websockets
import repositories.crud as crud
import services.room_service as room_service
from models.domain import RoomStatus
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
async def create_room_endpoint(room_data: CreateRoomRequest):
    await room_service.ensure_user_display_name(
        room_data.user_id, room_data.display_name
    )
    await room_service.ensure_provider_exists(room_data.supported_provider_id)

    try:
        room = await crud.create_room(
            room_data.name,
            room_data.user_id,
            room_data.supported_provider_id,
        )
        await room_service.ensure_active_membership(room_data.user_id, room.roomId)
        await room_service.refresh_room_state(room.roomId, "room_created")
        return {
            "success": True,
            "message": f"Successfully created room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=400, detail="Room already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


@router.post("/join_room", response_model=RoomResponse)
async def join_room(room_data: RoomRequest):
    if room_data.display_name is None or not room_data.display_name.strip():
        raise HTTPException(status_code=400, detail="Display name is required")

    normalized_code = room_data.join_code.strip().upper()
    if not room_service.JOIN_CODE_RE.match(normalized_code):
        raise HTTPException(
            status_code=422,
            detail="Join code must be exactly 6 characters (A-Z, 2-9, no I/O/0/1).",
        )

    await room_service.ensure_user_display_name(
        room_data.user_id, room_data.display_name
    )

    room = await crud.get_room_by_join_code(normalized_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(
            status_code=410,
            detail="This session has ended and is no longer available.",
        )

    try:
        await room_service.ensure_active_membership(room_data.user_id, room.roomId)
        await room_service.refresh_room_state(room.roomId, "participant_joined")
        await websockets.send_room_state(room.roomId)
        return {
            "success": True,
            "message": f"Successfully joined room {room.roomId}",
            "room_id": room.roomId,
            "join_code": room.joinCode,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join room: {str(e)}")


@router.post("/leave_room", response_model=RoomResponse)
async def leave_room(room_data: LeaveRoomRequest):
    try:
        await room_service.leave_room_service(room_data.room_id, room_data.user_id)
        await websockets.send_room_state(room_data.room_id)
        return {
            "success": True,
            "message": f"Successfully left room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


@router.post("/delete_room", response_model=RoomResponse)
async def delete_room(room_data: DeleteRoomRequest):
    try:
        await room_service.delete_room_service(room_data.room_id, room_data.user_id)
        await websockets.send_room_state(room_data.room_id)
        return {
            "success": True,
            "message": f"Successfully deleted room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete room: {str(e)}")


@router.post("/rooms/availability", response_model=RoomAvailabilityResponse)
async def rooms_availability(payload: RoomAvailabilityRequest):
    available, unavailable = await room_service.check_room_availability(
        payload.join_codes
    )
    return RoomAvailabilityResponse(
        available_join_codes=available,
        unavailable_join_codes=unavailable,
    )
