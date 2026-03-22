import json
import os
from collections import defaultdict
from datetime import datetime

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from db_utils import (
    create_room,
    create_room_membership,
    create_user,
    get_room,
    get_user,
)
from db_utils import leave_room as db_leave_room
from models import (
    AuthRequest,
    AuthResponse,
    CreateRoomRequest,
    RoomRequest,
    RoomResponse,
    Track,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # SvelteKit dev server
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Save the active websocket connections
active_room_connections: dict[str, set] = defaultdict(set)
generic_connections: set = set()

# Room state cache
room_state_cache: dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/hello")
async def root():
    return {"message": "Hello World"}


@app.get("/db-health")
async def db_health():
    # During unit test collection or in environments without a configured
    # DATABASE_URL we should avoid attempting a real database connection.
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return {"db-status": "skipped", "reason": "DATABASE_URL not configured"}

    # If DATABASE_URL is present, attempt a real check. Catch exceptions and
    # return an error status instead of letting the error propagate.
    try:
        conn = await asyncpg.connect(database_url)
        try:
            resp = await conn.fetchval("SELECT 1")
        finally:
            await conn.close()
    except Exception as e:
        return {"db-status": "error", "reason": str(e)}

    if resp == 1:
        return {"db-status": "ok"}
    return {"db-status": "error"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    active_room_connections[room_id].add(websocket)

    # Send the current room state to the newly connected client
    if room_id in room_state_cache:
        import json

        await websocket.send_text(json.dumps(room_state_cache[room_id]))

    try:
        while True:
            data = await websocket.receive_text()
            await handle_room_events(room_id, data)
            # Send new room state to users
            await send_room_state(room_id)
    finally:
        active_room_connections[room_id].remove(websocket)


async def handle_room_events(room_id: str, data: str):
    """Handle room events based on event type"""
    try:
        event = json.loads(data)
    except json.JSONDecodeError:
        print(f"Invalid JSON received: {data}")
        return

    event_type = event.get("type")

    if event_type == "addqueue":
        track_data = event.get("track")
        user_id = event.get("user_id")

        # Validate room exists
        if room_id not in room_state_cache:
            print(f"Error: Room {room_id} does not exist")
            return

        # Look up user's display name from room state
        display_name = user_id  # fallback to user_id
        for user_entry in room_state_cache[room_id].get("users", []):
            if user_entry.get("user", {}).get("userId") == user_id:
                display_name = user_entry.get("user", {}).get("displayName", user_id)
                break

        if track_data:
            try:
                track = Track(**track_data)
                await add_to_queue(
                    room_id=room_id,
                    track=track,
                    user_id=user_id,
                    display_name=display_name,
                )
            except ValueError as e:
                print(f"Error adding to queue: {e}")
            except Exception as e:
                print(f"Unexpected error adding to queue: {e}")


async def add_to_queue(
    room_id: str,
    track: Track,
    user_id: str,
    display_name: str,
):
    # TODO: Add check if song exists
    """Add a song to the room's queue"""
    if room_id not in room_state_cache:
        raise ValueError(f"Room {room_id} does not exist")

    if "queue" not in room_state_cache[room_id]:
        room_state_cache[room_id]["queue"] = []

    # Generate unique queue entry ID and determine position
    queue_count = len(room_state_cache[room_id]["queue"])
    queue_entry_id = f"QENTRY{queue_count + 1:03d}"
    position = queue_count + 1

    queue_entry = {
        "queueEntryId": queue_entry_id,
        "track": track.dict(),
        "addedBy": {
            "userId": user_id,
            "displayName": display_name,
        },
        "queuedAt": str(datetime.utcnow()),
        "position": position,
        "status": "queued",
        "voteScore": 0,
        "orderRank": position,
        "feedback": [],
    }

    room_state_cache[room_id]["queue"].append(queue_entry)


# Dummy authenticaiton endpoints
@app.post("/auth/account", response_model=AuthResponse)
async def auth_account(auth_data: AuthRequest):
    """Dummy endpoint for account authentication"""
    # In a real implementation, this would validate credentials against a database
    return {
        "success": True,
        "message": "Account authentication successful",
        "token": "dummy_account_token_12345",
    }


# Room management endpoints
@app.post("/create_room", response_model=RoomResponse)
async def create_room_endpoint(room_data: CreateRoomRequest):
    """Endpoint for creating a new room"""
    # Check if user exists, create if not
    user = await get_user(room_data.user_id)
    if not user:
        try:
            await create_user(room_data.user_id, room_data.user_id)
            user = await get_user(room_data.user_id)
        except ValueError:
            # User might have been created by another request, try to get it
            user = await get_user(room_data.user_id)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to create user: {str(e)}"
            )

    # Ensure user exists
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create or retrieve user")

    # Create the room
    try:
        room = await create_room(
            room_data.room_id,
            room_data.name,
            room_data.user_id,
            room_data.supported_provider_id,
        )

        # Initialize room state cache
        if room_data.room_id not in room_state_cache:
            room_state_cache[room_data.room_id] = {
                "room": {
                    "roomId": room.roomId,
                    "joinCode": room.joinCode,
                    "name": room.name,
                    "status": room.status.value,
                    "createdAt": str(room.createdAt),
                },
                "host": {
                    "userId": user.userId,
                    "displayName": user.displayName,
                    "createdAt": str(user.createdAt),
                },
                "users": [],
                "queue": [],
            }

        return {
            "success": True,
            "message": f"Successfully created room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=400, detail="Room already exists")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")


@app.post("/join_room", response_model=RoomResponse)
async def join_room(room_data: RoomRequest):
    """Endpoint for joining a room"""
    # Check if user exists, create if not
    user = await get_user(room_data.user_id)
    if not user:
        try:
            await create_user(room_data.user_id, room_data.user_id)
        except ValueError as e:
            if "already exists" in str(e):
                # User was created by another request
                pass
            else:
                raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to create user: {str(e)}"
            )

    # Check if room exists
    room = await get_room(room_data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify room exists in cache
    if room_data.room_id not in room_state_cache:
        raise HTTPException(status_code=404, detail="Room state not initialized")

    # Create room membership
    try:
        await create_room_membership(room_data.user_id, room_data.room_id)

        if "users" not in room_state_cache[room_data.room_id]:
            room_state_cache[room_data.room_id]["users"] = []

        # Add the new member to the users list
        room_state_cache[room_data.room_id]["users"].append(
            {
                "user": {
                    "userId": room_data.user_id,
                    "displayName": room_data.user_id,
                    "createdAt": str(datetime.utcnow()),
                },
                "membership": {
                    "joinedAt": str(datetime.utcnow()),
                    "leftAt": None,
                    "membershipStatus": "active",
                },
            }
        )

        # Broadcast updated room state to all connected clients
        await send_room_state(room_data.room_id)

        return {
            "success": True,
            "message": f"Successfully joined room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except ValueError as e:
        if "already a member" in str(e):
            raise HTTPException(
                status_code=400, detail="User is already a member of this room"
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join room: {str(e)}")


@app.post("/leave_room", response_model=RoomResponse)
async def leave_room(room_data: RoomRequest):
    """Endpoint for leaving a room"""
    # Check if user exists
    user = await get_user(room_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if room exists
    room = await get_room(room_data.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify room exists in cache
    if room_data.room_id not in room_state_cache:
        raise HTTPException(status_code=404, detail="Room state not initialized")

    # Remove user from room membership
    try:
        await db_leave_room(room_data.user_id, room_data.room_id)

        # Update room state cache - update user's membership status
        if "users" in room_state_cache[room_data.room_id]:
            for user_entry in room_state_cache[room_data.room_id]["users"]:
                if user_entry.get("user", {}).get("userId") == room_data.user_id:
                    if "membership" not in user_entry:
                        user_entry["membership"] = {}
                    user_entry["membership"]["leftAt"] = str(datetime.utcnow())
                    user_entry["membership"]["membershipStatus"] = "inactive"
                    break

        # Broadcast updated room state to all connected clients
        await send_room_state(room_data.room_id)

        return {
            "success": True,
            "message": f"Successfully left room {room_data.room_id}",
            "room_id": room_data.room_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave room: {str(e)}")


async def send_room_state(room_id: str):
    # Broadcast to all connections in the room
    if room_id in active_room_connections:
        import json

        room_state = room_state_cache.get(room_id, {})
        for websocket in active_room_connections[room_id]:
            try:
                await websocket.send_text(json.dumps(room_state))
            except Exception as e:
                print(f"Error sending to websocket: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    generic_connections.add(websocket)

    try:
        while True:
            await websocket.receive_text()
            await websocket.send_text("No detail provided")
    finally:
        generic_connections.remove(websocket)


# TODO: Add logic to test songs exist
async def check_song_exists(access_token: str, endpoint: str, song_id: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            return {"status": "success", "data": response.json()}
    except httpx.HTTPStatusError as e:
        return {
            "status": "error",
            "error": str(e),
            "status_code": e.response.status_code,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
