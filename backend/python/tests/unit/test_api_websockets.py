import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from api.websockets import (
    active_room_connections,
    heartbeat_loop,
    router,
    send_room_state,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_websocket_room_connection(app):
    """Verify that connecting to a room WS endpoint sends initial state."""
    mock_state = {"room": {"roomId": "r1"}}

    with (
        patch("services.room_state_service.room_state_cache", {"r1": mock_state}),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch("api.websockets.heartbeat_loop", new_callable=AsyncMock),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws/r1") as websocket:
            data = websocket.receive_text()
            assert json.loads(data) == mock_state
            assert len(active_room_connections["r1"]) == 1


@pytest.mark.asyncio
async def test_websocket_generic_connection(app):
    """Verify generic websocket connection."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("hello")
        data = websocket.receive_text()
        assert data == "No detail provided"


@pytest.mark.asyncio
async def test_heartbeat_loop_timeout():
    """Verify that heartbeat_loop closes websocket on timeout."""

    mock_ws = AsyncMock(spec=WebSocket)
    mock_pong = MagicMock(spec=asyncio.Event)
    mock_pong.wait = AsyncMock(side_effect=asyncio.TimeoutError)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # We need to break the loop or it will run forever
        # Using side_effect to raise an exception after one iteration
        mock_ws.send_text.side_effect = [None, Exception("break")]

        try:
            await heartbeat_loop(mock_ws, mock_pong)
        except Exception:
            pass

        mock_ws.close.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_identify(app):
    """Verify that identify event updates user_id in active_room_connections."""
    mock_state = {"room": {"roomId": "r1"}}

    with (
        patch("services.room_state_service.room_state_cache", {"r1": mock_state}),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch(
            "services.room_service.ensure_active_membership", new_callable=AsyncMock
        ) as mock_ensure,
        patch("services.room_service.handle_disconnect", new_callable=AsyncMock),
        patch("api.websockets.heartbeat_loop", new_callable=AsyncMock),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws/r1") as websocket:
            # Skip initial state
            websocket.receive_text()

            websocket.send_text(json.dumps({"type": "identify", "user_id": "u1"}))

            # Initial state again after identify (force_refresh=True)
            websocket.receive_text()

            mock_ensure.assert_called_once_with("u1", "r1")
            # Verify user_id is set for this websocket
            for ws, uid in active_room_connections["r1"].items():
                if uid == "u1":
                    break
            else:
                pytest.fail("user_id not found in active_room_connections")


@pytest.mark.asyncio
async def test_websocket_dispatch(app):
    """Verify that generic events are dispatched."""
    mock_state = {"room": {"roomId": "r1"}}

    with (
        patch("services.room_state_service.room_state_cache", {"r1": mock_state}),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch("api.websockets.dispatch", new_callable=AsyncMock) as mock_dispatch,
        patch("api.websockets.heartbeat_loop", new_callable=AsyncMock),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws/r1") as websocket:
            # Skip initial state
            websocket.receive_text()

            websocket.send_text(json.dumps({"type": "some_event", "data": "value"}))

            # After dispatch, send_room_state is called
            websocket.receive_text()

            mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_send_room_state_broadcasting():
    """Unit test for send_room_state logic directly."""

    mock_ws1 = AsyncMock(spec=WebSocket)
    mock_ws2 = AsyncMock(spec=WebSocket)

    active_room_connections["r2"] = {mock_ws1: "u1", mock_ws2: "u2"}
    mock_state = {"foo": "bar"}

    with patch("services.room_state_service.room_state_cache", {"r2": mock_state}):
        await send_room_state("r2")

        mock_ws1.send_text.assert_called_once_with(json.dumps(mock_state))
        mock_ws2.send_text.assert_called_once_with(json.dumps(mock_state))
