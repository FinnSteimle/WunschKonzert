import os

import asyncpg
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # SvelteKit dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def websocket_endpoint_room(websocket, room_id: str):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data} for room {room_id}")


@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    while True:
        await websocket.receive_text()
        await websocket.send_text("No detail provided")


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
