import os
from collections import defaultdict

import asyncpg
import httpx
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from models import AuthRequest, AuthResponse, RoomRequest, RoomResponse

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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/hello")
async def root():
    return {"message": "Hello World"}


@app.get("/db-health")
async def db_health():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        resp = await conn.fetchval("SELECT 1")
    finally:
        await conn.close()

    if resp == 1:
        return {"db-status": "ok"}
    return {"db-status": "error"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    active_room_connections[room_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data} for room {room_id}")
    finally:
        active_room_connections[room_id].remove(websocket)


# Dummy authentication endpoints
@app.post("/auth/account", response_model=AuthResponse)
async def auth_account(auth_data: AuthRequest):
    """Dummy endpoint for account authentication"""
    # In a real implementation, this would validate credentials against a database
    return {
        "success": True,
        "message": "Account authentication successful",
        "token": "dummy_account_token_12345",
    }


@app.post("/auth/user", response_model=AuthResponse)
async def auth_user(auth_data: AuthRequest):
    """Dummy endpoint for user authentication"""
    # In a real implementation, this would validate credentials
    return {
        "success": True,
        "message": "User authentication successful",
        "token": "dummy_user_token_67890",
    }


# Room management endpoints
@app.post("/join_room", response_model=RoomResponse)
async def join_room(room_data: RoomRequest):
    """Dummy endpoint for joining a room"""
    # In a real implementation, this would add user to room in database
    return {
        "success": True,
        "message": f"Successfully joined room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


@app.post("/leave_room", response_model=RoomResponse)
async def leave_room(room_data: RoomRequest):
    """Dummy endpoint for leaving a room"""
    # In a real implementation, this would remove user from room in database
    return {
        "success": True,
        "message": f"Successfully left room {room_data.room_id}",
        "room_id": room_data.room_id,
    }


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
