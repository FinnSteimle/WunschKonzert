"""
WebSocket Event Dispatcher
==========================

This module implements a dispatch-table pattern for routing incoming WebSocket
messages to their handler functions. It replaces a growing if/elif chain in a
single function with a dictionary lookup, keeping complexity flat regardless of
how many event types exist.

HOW IT WORKS
------------
1. A shared dict `_HANDLERS` maps event-type strings to async handler functions:

       _HANDLERS = {
           "vote":     _handle_vote,
           "addqueue": _handle_addqueue,
           ...
       }

2. The `@register("event_type")` decorator populates that dict at import time.
   When Python loads this module it executes every @register decorator, so by
   the time `dispatch()` is first called the table is already fully built.

3. `dispatch()` parses the raw JSON string, looks up the handler in O(1), and
   calls it. It never needs to know about individual event types — adding a new
   event is just adding a new @register function here, nothing else changes.

WHY A DECORATOR FACTORY
-----------------------
A plain decorator (@register) cannot accept arguments. We need to pass the
event-type string, so we use a factory: `register("vote")` returns a decorator,
and that decorator receives the function and stores it in _HANDLERS.

    @register("vote")           # 1. register("vote") is called → returns decorator
    async def _handle_vote(...) # 2. decorator(_handle_vote) is called
                                #    → stores _handle_vote in _HANDLERS["vote"]
                                #    → returns _handle_vote unchanged

ADDING A NEW EVENT TYPE
-----------------------
    @register("my_new_event")
    async def _handle_my_new_event(room_id: str, event: dict) -> None:
        await room_service.my_new_service_function(
            room_id, event.get("some_field")
        )

That's it. No other file needs to change.
"""

import json
from collections.abc import Awaitable
from typing import Callable

import services.host_transfer_service as host_transfer_service
import services.room_service as room_service

# Type alias: every handler takes (room_id, event_dict) and returns nothing (async)
EventHandler = Callable[[str, dict[str, object]], Awaitable[None]]

_HANDLERS: dict[str, EventHandler] = {}


def register(event_type: str) -> Callable[[EventHandler], EventHandler]:
    """Decorator factory that registers a handler for a given event type."""

    def decorator(fn: EventHandler) -> EventHandler:
        _HANDLERS[event_type] = fn
        return fn

    return decorator


@register("addqueue")
async def _handle_addqueue(room_id: str, event: dict[str, object]) -> None:
    track = event.get("track")
    user_id = str(event.get("user_id", ""))
    if not isinstance(track, dict):
        return
    await room_service.add_to_queue(room_id, track, user_id)


@register("remove_queue_entry")
async def _handle_remove_queue_entry(room_id: str, event: dict[str, object]) -> None:
    await room_service.remove_queue_entry(
        room_id=room_id,
        queue_entry_id=str(event.get("queue_entry_id", "")),
        user_id=str(event.get("user_id", "")),
    )


@register("vote")
async def _handle_vote(room_id: str, event: dict[str, object]) -> None:
    await room_service.vote_queue_entry(
        room_id=room_id,
        queue_entry_id=str(event.get("queue_entry_id", "")),
        user_id=str(event.get("user_id", "")),
        vote_type=str(event.get("vote_type", "neutral")),
    )


@register("playback")
async def _handle_playback(room_id: str, event: dict[str, object]) -> None:
    position_ms = event.get("position_ms")
    await room_service.set_playback_state(
        room_id=room_id,
        user_id=str(event.get("user_id", "")),
        action=str(event.get("action", "")),
        position_ms=int(position_ms) if isinstance(position_ms, (int, float)) else None,
    )


@register("position_sync")
async def _handle_position_sync(room_id: str, event: dict[str, object]) -> None:
    pos = event.get("position_ms")
    if isinstance(pos, (int, float)):
        await room_service.sync_playback_position(
            room_id, str(event.get("user_id", "")), int(pos)
        )


@register("history")
async def _handle_get_history(room_id: str, event: dict[str, object]) -> None:
    await room_service.get_song_history(room_id)


@register("rename")
async def _handle_rename(room_id: str, event: dict[str, object]) -> None:
    await room_service.rename_participant(
        room_id=room_id,
        user_id=str(event.get("user_id", "")),
        display_name=str(event.get("display_name", "")),
    )


@register("leave")
async def _handle_leave(room_id: str, event: dict[str, object]) -> None:
    await room_service.leave_room_service(room_id, str(event.get("user_id", "")))


@register("host_transfer_initiate")
async def _handle_host_transfer_initiate(
    room_id: str, event: dict[str, object]
) -> None:
    await host_transfer_service.initiate_transfer(
        room_id=room_id,
        from_user_id=str(event.get("from_user_id", "")),
        to_user_id=str(event.get("to_user_id", "")),
    )


@register("host_transfer_accept")
async def _handle_host_transfer_accept(room_id: str, event: dict[str, object]) -> None:
    await host_transfer_service.accept_transfer(
        room_id=room_id,
        transfer_id=str(event.get("transfer_id", "")),
        user_id=str(event.get("user_id", "")),
    )


@register("host_transfer_reject")
async def _handle_host_transfer_reject(room_id: str, event: dict[str, object]) -> None:
    await host_transfer_service.reject_transfer(
        room_id=room_id,
        transfer_id=str(event.get("transfer_id", "")),
        user_id=str(event.get("user_id", "")),
    )


async def dispatch(room_id: str, data: str) -> None:
    """Parse an incoming WebSocket message and dispatch to the registered handler."""
    try:
        event: dict[str, object] = json.loads(data)
    except json.JSONDecodeError:
        print(f"Invalid JSON received: {data}")
        return

    event_type = event.get("type")
    handler = _HANDLERS.get(str(event_type)) if event_type is not None else None

    if handler is None:
        print(f"Unknown event type: {event_type}")
        return

    try:
        await handler(room_id, event)
    except Exception as e:
        print(f"Error handling room event '{event_type}': {e}")
