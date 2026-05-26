import json
from unittest.mock import AsyncMock, patch

import pytest

from api.event_handlers import dispatch

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dispatch_addqueue():
    room_id = "r1"
    event = {"type": "addqueue", "track": {"trackId": "t1"}, "user_id": "u1"}
    with patch(
        "services.queue_service.add_to_queue", new_callable=AsyncMock
    ) as mock_service:
        await dispatch(room_id, json.dumps(event))
        mock_service.assert_called_once_with(room_id, event["track"], event["user_id"])


@pytest.mark.asyncio
async def test_dispatch_vote():
    room_id = "r1"
    event = {
        "type": "vote",
        "queue_entry_id": "qe1",
        "user_id": "u1",
        "vote_type": "like",
    }
    with patch(
        "services.vote_service.vote_queue_entry", new_callable=AsyncMock
    ) as mock_service:
        await dispatch(room_id, json.dumps(event))
        mock_service.assert_called_once_with(
            room_id=room_id, queue_entry_id="qe1", user_id="u1", vote_type="like"
        )


@pytest.mark.asyncio
async def test_dispatch_playback():
    room_id = "r1"
    event = {
        "type": "playback",
        "action": "pause",
        "user_id": "u1",
        "position_ms": 1000,
    }
    with patch(
        "services.playback_service.set_playback_state", new_callable=AsyncMock
    ) as mock_service:
        await dispatch(room_id, json.dumps(event))
        mock_service.assert_called_once_with(
            room_id=room_id,
            user_id="u1",
            action="pause",
            position_ms=1000,
            queue_entry_id=None,
        )


@pytest.mark.asyncio
async def test_dispatch_invalid_json():
    with patch("builtins.print") as mock_print:
        await dispatch("r1", "{invalid}")
        mock_print.assert_any_call("Invalid JSON received: {invalid}")


@pytest.mark.asyncio
async def test_dispatch_unknown_type():
    with patch("builtins.print") as mock_print:
        await dispatch("r1", json.dumps({"type": "unknown"}))
        mock_print.assert_any_call("Unknown event type: unknown")


@pytest.mark.asyncio
async def test_dispatch_remove_queue_entry():
    event = {"type": "remove_queue_entry", "queue_entry_id": "qe1", "user_id": "u1"}
    with patch(
        "services.queue_service.remove_queue_entry", new_callable=AsyncMock
    ) as mock_service:
        await dispatch("r1", json.dumps(event))
        mock_service.assert_called_once_with(
            room_id="r1", queue_entry_id="qe1", user_id="u1"
        )


@pytest.mark.asyncio
async def test_dispatch_position_sync():
    event = {
        "type": "position_sync",
        "user_id": "u1",
        "position_ms": 1000,
        "queue_entry_id": "qe1",
    }
    with patch(
        "services.playback_service.sync_playback_position", new_callable=AsyncMock
    ) as mock_service:
        await dispatch("r1", json.dumps(event))
        mock_service.assert_called_once_with("r1", "u1", 1000, queue_entry_id="qe1")


@pytest.mark.asyncio
async def test_dispatch_rename():
    event = {"type": "rename", "user_id": "u1", "display_name": "New Name"}
    with patch(
        "services.room_service.rename_participant", new_callable=AsyncMock
    ) as mock_service:
        await dispatch("r1", json.dumps(event))
        mock_service.assert_called_once_with(
            room_id="r1", user_id="u1", display_name="New Name"
        )


@pytest.mark.asyncio
async def test_dispatch_host_transfer_initiate():
    event = {"type": "host_transfer_initiate", "from_user_id": "u1", "to_user_id": "u2"}
    with patch(
        "services.host_transfer_service.initiate_transfer", new_callable=AsyncMock
    ) as mock_service:
        await dispatch("r1", json.dumps(event))
        mock_service.assert_called_once_with(
            room_id="r1", from_user_id="u1", to_user_id="u2"
        )


@pytest.mark.asyncio
async def test_dispatch_handler_exception():
    event = {"type": "leave", "user_id": "u1"}
    with (
        patch("services.room_service.leave_room", side_effect=Exception("boom")),
        patch("builtins.print") as mock_print,
    ):
        await dispatch("r1", json.dumps(event))
        mock_print.assert_any_call("Error handling room event 'leave': boom")
