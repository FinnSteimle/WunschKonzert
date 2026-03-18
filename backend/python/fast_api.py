import os

import asyncpg
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
async def websocket_endpoint(websocket, room_id:str):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data} for room {room_id}")