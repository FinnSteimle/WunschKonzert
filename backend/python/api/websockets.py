import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

import services.room_service as room_service
from api.event_handlers import dispatch

router = APIRouter()

# room_id -> {websocket: user_id}
active_room_connections: dict[str, dict[WebSocket, str | None]] = defaultdict(dict)
generic_connections: set[WebSocket] = set()


async def send_room_state(room_id: str, force_refresh: bool = False) -> None:
    # Optimization: If no one is connected to this room, we don't need to rebuild the state.
    # We just clear the cache so it's fresh when someone eventually connects.
    if room_id not in active_room_connections:
        if force_refresh:
            room_service.room_state_cache.pop(room_id, None)
        return

    # If it's not in cache or we want to force a refresh, we rebuild it.
    if force_refresh or room_id not in room_service.room_state_cache:
        try:
            await room_service.refresh_room_state(room_id)
        except Exception as e:
            print(f"Error refreshing room state for {room_id}: {e}")
            return

    state = room_service.room_state_cache.get(room_id, None)
    if state is None:
        return

    for websocket in list(active_room_connections[room_id].keys()):
        try:
            await websocket.send_text(json.dumps(state))
        except Exception as e:
            print(f"Error sending to websocket: {e}")
            active_room_connections[room_id].pop(websocket, None)


async def heartbeat_loop(websocket: WebSocket, pong_event: asyncio.Event) -> None:
    """Send a ping every 30s and wait for a pong. Close if no pong arrives."""
    try:
        while True:
            await asyncio.sleep(30)
            pong_event.clear()
            try:
                await websocket.send_text("ping")
                await asyncio.wait_for(pong_event.wait(), timeout=10.0)
            except asyncio.TimeoutError, Exception:
                await websocket.close()
                break
    except Exception:
        pass


@router.websocket("/ws/{room_id}")
async def websocket_endpoint_room(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    active_room_connections[room_id][websocket] = None
    await send_room_state(room_id)

    pong_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(heartbeat_loop(websocket, pong_event))

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            if data == "pong":
                pong_event.set()
                continue

            # Peek for identity message
            try:
                event = json.loads(data)
                if event.get("type") == "identify":
                    user_id = str(event.get("user_id", ""))
                    active_room_connections[room_id][websocket] = user_id
                    # Ensure they are marked active in DB upon connection/identification
                    await room_service.ensure_active_membership(user_id, room_id)
                    await send_room_state(room_id, force_refresh=True)
                    continue
            except json.JSONDecodeError, TypeError:
                pass

            await dispatch(room_id, data)
            await send_room_state(room_id, force_refresh=False)
    finally:
        heartbeat_task.cancel()
        disconnected_user_id = active_room_connections[room_id].pop(websocket, None)
        if disconnected_user_id:
            await room_service.handle_disconnect(room_id, disconnected_user_id)
            await send_room_state(room_id, force_refresh=False)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    generic_connections.add(websocket)
    try:
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            await websocket.send_text("No detail provided")
    finally:
        generic_connections.discard(websocket)
