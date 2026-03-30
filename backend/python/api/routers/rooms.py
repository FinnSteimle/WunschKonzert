from fastapi import APIRouter, HTTPException
from models.schemas import (
    CreateRoomRequest,
    RoomRequest,
    RoomResponse,
    LeaveRoomRequest,
    DeleteRoomRequest,
)
from models.domain import RoomStatus
import repositories.crud as crud
import services.room_service as room_service
import api.websockets as websockets

router = APIRouter()


@router.post("/create_room", response_model=RoomResponse)
async def create_room_endpoint(room_data: CreateRoomRequest):
    await room_service.ensure_user_display_name(room_data.user_id, room_data.display_name)
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
    await room_service.ensure_user_display_name(room_data.user_id, room_data.display_name)

    room = await crud.get_room_by_join_code(room_data.room_id.upper())
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if room.status != RoomStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Room is not active")

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
    user = await crud.get_user(room_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    room = await crud.get_room(room_data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    try:
        await room_service.leave_room_service(room_data.room_id, room_data.user_id)
        await websockets.send_room_state(room_data.room_id)
        return {
            "success": True,
            "message": f"Successfully left room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


@router.post("/delete_room", response_model=RoomResponse)
async def delete_room(room_data: DeleteRoomRequest):
    await room_service.delete_room_service(room_data.room_id, room_data.user_id)
    await websockets.send_room_state(room_data.room_id)
    return {
        "success": True,
        "message": f"Successfully deleted room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


@router.get("/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    room_state = await room_service.refresh_room_state(room_id)
    return room_state


@router.post("/rooms/{room_id}/queue")
async def add_queue_entry(room_id: str, event: dict):
    track_data = event.get("track")
    user_id = event.get("user_id")
    room_state = await room_service.add_to_queue(room_id, track_data, user_id)
    await websockets.send_room_state(room_id)
    return {"success": True, "room": room_state}
