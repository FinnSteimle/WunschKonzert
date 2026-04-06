import json
from collections import defaultdict

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

import services.room_service as room_service

router = APIRouter()

active_room_connections: dict[str, set[WebSocket]] = defaultdict(set)
generic_connections: set[WebSocket] = set()


async def send_room_state(room_id: str) -> None:
    if room_id not in room_service.room_state_cache:
        try:
            await room_service.refresh_room_state(room_id)
        except Exception as e:
            print(f"Error refreshing room state for {room_id}: {e}")
            return

    state = room_service.room_state_cache.get(room_id, None)
    if state is None:
        return

    if room_id in active_room_connections:
        for websocket in list(active_room_connections[room_id]):
            try:
                await websocket.send_text(json.dumps(state))
            except Exception as e:
                print(f"Error sending to websocket: {e}")
                active_room_connections[room_id].discard(websocket)


async def handle_room_events(room_id: str, data: str) -> None:
    try:
        event = json.loads(data)
    except json.JSONDecodeError:
        print(f"Invalid JSON received: {data}")
        return

    event_type = event.get("type")
    try:
        if event_type == "addqueue":
            await room_service.add_to_queue(
                room_id, event.get("track"), event.get("user_id")
            )
        elif event_type == "vote":
            await room_service.vote_queue_entry(
                room_id=room_id,
                queue_entry_id=event.get("queue_entry_id"),
                user_id=event.get("user_id"),
                vote_type=event.get("vote_type", "neutral"),
            )
        elif event_type == "playback":
            await room_service.set_playback_state(
                room_id=room_id,
                user_id=event.get("user_id"),
                action=event.get("action"),
            )
        elif event_type == "rename":
            await room_service.rename_participant(
                room_id=room_id,
                user_id=event.get("user_id"),
                display_name=event.get("display_name", ""),
            )
        elif event_type == "leave":
            await room_service.leave_room_service(room_id, event.get("user_id"))
    except Exception as e:
        print(f"Error handling room event: {e}")


@router.websocket("/ws/{room_id}")
async def websocket_endpoint_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    active_room_connections[room_id].add(websocket)
    await send_room_state(room_id)

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            await handle_room_events(room_id, data)
            await send_room_state(room_id)
    finally:
        active_room_connections[room_id].discard(websocket)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
