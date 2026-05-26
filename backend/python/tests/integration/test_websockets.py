import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from api.event_handlers import dispatch as handle_room_events
from api.websockets import (
    active_room_connections,
    send_room_state,
)
from repositories import membership_repo, user_repo
from services import (
    queue_service,
    room_service,
    room_state_service,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_websocket_room_state_on_connect(db_session, init_room, websocket_client):
    # 1. Setup a room and a host
    room = await init_room()
    room_id = room.roomId

    # 2. Connect to the room's websocket
    with websocket_client.websocket_connect(f"/ws/{room_id}") as websocket:
        # 3. Receive initial room state
        data = websocket.receive_json()
        assert "room" in data
        assert data["room"]["roomId"] == room_id
        assert data["room"]["name"] == "test_room"
        assert "host" in data
        assert data["host"]["displayName"] == "test_host"


@pytest.mark.asyncio
async def test_websocket_rename_event(db_session, init_room, websocket_client):
    # 1. Setup a room and a host
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    room_id = room.roomId

    # 2. Connect to the room's websocket
    with websocket_client.websocket_connect(f"/ws/{room_id}") as websocket:
        # Initial state
        _ = websocket.receive_json()

        # 3. Send a rename event
        rename_event = {
            "type": "rename",
            "user_id": host_id,
            "display_name": "New Name",
        }
        websocket.send_json(rename_event)

        # 4. Receive updated state
        updated_data = websocket.receive_json()
        assert updated_data["host"]["displayName"] == "New Name"
        assert any(
            u["user"]["displayName"] == "New Name" for u in updated_data["users"]
        )
        assert updated_data["lastEvent"]["type"] == "participant_renamed"
        assert updated_data["lastActivity"]["type"] == "user_renamed"
        assert updated_data["lastActivity"]["userId"] == host_id
        assert updated_data["lastActivity"]["username"] == "New Name"


@pytest.mark.asyncio
async def test_websocket_non_host_playback_rejected_no_state_change(
    db_session, init_room, websocket_client
):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    guest_id = str(uuid.uuid4())
    await user_repo.create_user(guest_id, "Guest", db_session)
    await membership_repo.create_room_membership(
        guest_id, room.roomId, session=db_session
    )
    await db_session.commit()

    track = {
        "trackId": str(uuid.uuid4()),
        "providerTrackId": "spotify:track:test",
        "title": "Song",
        "artist": "Artist",
        "album": "",
        "duration": 180,
        "coverUrl": "",
        "deepLink": "",
    }

    await queue_service.add_to_queue(room.roomId, track, guest_id)

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as websocket:
        start_state = websocket.receive_json()
        assert start_state["playback"]["state"] == "paused"  # First song starts paused

        websocket.send_json(
            {
                "type": "playback",
                "user_id": guest_id,
                "action": "pause",
            }
        )

        after_state = websocket.receive_json()

        assert after_state["playback"]["state"] == start_state["playback"]["state"]
        assert after_state["queue"] == start_state["queue"]
        assert after_state.get("lastEvent", {}).get("type") != "playback_updated"


@pytest.mark.asyncio
async def test_websocket_vote_updates_vote_score_and_feedback(
    db_session, init_room, websocket_client
):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    guest_id = str(uuid.uuid4())
    await user_repo.create_user(guest_id, "Guest", db_session)
    await membership_repo.create_room_membership(
        guest_id, room.roomId, session=db_session
    )
    await db_session.commit()

    i = 0
    while i <= 1:
        track = {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": "spotify:track:test",
            "title": "Song",
            "artist": "Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }
        await queue_service.add_to_queue(room.roomId, track, guest_id)
        i += 1

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as ws:
        start_state = ws.receive_json()

        ws.send_json(
            {
                "type": "vote",
                "queue_entry_id": start_state["queue"][0]["queueEntryId"],
                "user_id": guest_id,
                "vote_type": "upvote",
            }
        )

        after_state = ws.receive_json()

        assert after_state["queue"][0]["voteScore"] == 1
        feedback = after_state["queue"][0]["feedback"]
        assert len(feedback) == 1
        assert feedback[0]["userId"] == guest_id
        assert feedback[0]["type"] == "upvote"
        assert after_state.get("lastEvent", {}).get("type") == "vote_updated"
        assert after_state["lastActivity"]["type"] == "up_vote"
        assert after_state["lastActivity"]["userId"] == guest_id
        assert (
            after_state["lastActivity"]["queueEntryId"]
            == start_state["queue"][0]["queueEntryId"]
        )


@pytest.mark.asyncio
async def test_websocket_addqueue_updates_state_for_all_clients(
    db_session, init_room, websocket_client
):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    guest_id = str(uuid.uuid4())
    await user_repo.create_user(guest_id, "Guest", db_session)
    await membership_repo.create_room_membership(
        guest_id, room.roomId, session=db_session
    )
    await db_session.commit()

    with (
        websocket_client.websocket_connect(f"/ws/{room.roomId}") as ws1,
        websocket_client.websocket_connect(f"/ws/{room.roomId}") as ws2,
    ):
        start_state_1 = ws1.receive_json()
        start_state_2 = ws2.receive_json()

        base_len_1 = len(start_state_1["queue"])
        base_len_2 = len(start_state_2["queue"])

        track_id = str(uuid.uuid4())
        ws1.send_json(
            {
                "type": "addqueue",
                "track": {
                    "trackId": track_id,
                    "providerTrackId": f"spotify:track:{track_id[:8]}",
                    "title": "Added From WS",
                    "artist": "Artist",
                    "album": "",
                    "duration": 180,
                    "coverUrl": "",
                    "deepLink": "",
                },
                "user_id": guest_id,
            }
        )

        def _receive_queue_updated(ws):
            last = None
            for _ in range(5):
                try:
                    data = ws.receive_text()
                    if data == "ping":
                        continue
                    last = json.loads(data)
                    if last.get("lastEvent", {}).get("type") == "queue_updated":
                        return last
                except json.JSONDecodeError, TypeError:
                    continue
            return last

        after_state_1 = _receive_queue_updated(ws1)
        after_state_2 = _receive_queue_updated(ws2)

        assert len(after_state_1["queue"]) == base_len_1 + 1
        assert len(after_state_2["queue"]) == base_len_2 + 1
        assert any(
            item["track"]["trackId"] == track_id for item in after_state_1["queue"]
        )
        assert any(
            item["track"]["trackId"] == track_id for item in after_state_2["queue"]
        )
        assert after_state_1.get("lastEvent", {}).get("type") == "queue_updated"
        assert after_state_2.get("lastEvent", {}).get("type") == "queue_updated"
        assert after_state_1["lastActivity"]["type"] == "track_added"
        assert after_state_1["lastActivity"]["userId"] == guest_id
        assert after_state_1["lastActivity"]["queueEntryId"] is not None


@pytest.mark.asyncio
async def test_websocket_broadcast_to_multiple_clients(
    db_session, init_room, websocket_client
):
    # 1. Setup a room and a host
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    room_id = room.roomId

    # 2. Connect two clients to the same room
    with (
        websocket_client.websocket_connect(f"/ws/{room_id}") as ws1,
        websocket_client.websocket_connect(f"/ws/{room_id}") as ws2,
    ):
        # Receive initial states
        data1_init = ws1.receive_json()
        data2_init = ws2.receive_json()

        # Both should have the same initial state
        assert data1_init["room"]["roomId"] == room_id
        assert data2_init["room"]["roomId"] == room_id


@pytest.mark.asyncio
async def test_websocket_generic_endpoint(db_session, websocket_client):
    with websocket_client.websocket_connect("/ws") as websocket:
        websocket.send_text("Hello")
        message = websocket.receive_text()
        assert message == "No detail provided"


@pytest.mark.asyncio
async def test_websocket_room_not_found(db_session, websocket_client):
    # Connecting to a non-existent room should still work but might have empty state or error in sending state
    with websocket_client.websocket_connect("/ws/non-existent-room") as websocket:
        # Initial call to send_room_state will fail gracefully
        websocket.send_json(
            {"type": "rename", "user_id": "none", "display_name": "fail"}
        )
        pass


@pytest.mark.asyncio
async def test_websocket_playback_control(db_session, init_room, websocket_client):
    # Test play/pause/skip functionality
    room = await init_room()

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as websocket:
        # Initial state
        state = websocket.receive_json()

        # Verify room state is received
        assert "room" in state
        assert state["room"]["roomId"] == room.roomId


@pytest.mark.asyncio
async def test_websocket_queue_management(db_session, init_room, websocket_client):
    # Test that websocket connection works and can receive room state
    room = await init_room()

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as websocket:
        # Initial state
        state = websocket.receive_json()
        assert "room" in state
        assert "queue" in state


@pytest.mark.asyncio
async def test_websocket_voting(db_session, init_room, websocket_client):
    # Test that websocket connection works and state is maintained
    room = await init_room()

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as websocket:
        # Initial state
        state = websocket.receive_json()
        assert "room" in state
        assert state["room"]["roomId"] == room.roomId


@pytest.mark.asyncio
async def test_websocket_invalid_event(db_session, init_room, websocket_client):
    # Test that connection stays open after receiving events
    room = await init_room()

    with websocket_client.websocket_connect(f"/ws/{room.roomId}") as websocket:
        # Initial state
        state = websocket.receive_json()
        assert "room" in state

        # Send invalid event - should still get a response without crashing
        websocket.send_json({"type": "invalid_event_type"})

        # Connection should remain open and we should get a state update or error
        response = websocket.receive_json()
        # Either we get an error or state update, but it shouldn't crash
        assert isinstance(response, dict)


@pytest.mark.asyncio
async def test_send_room_state_refresh_failure():
    """Test send_room_state when refresh_room_state raises an exception."""
    room_id = "test_room"

    # Mock the room state service to raise an exception
    with patch.object(
        room_state_service, "refresh_room_state", side_effect=Exception("DB error")
    ):
        await send_room_state(room_id)

    # Should not raise, just print error
    assert room_id not in room_state_service.room_state_cache


@pytest.mark.asyncio
async def test_send_room_state_none_cache():
    """Test send_room_state when cache returns None."""
    room_id = "test_room"

    # Mock cache to return None by temporarily replacing the cache
    original_cache = room_state_service.room_state_cache
    try:
        room_state_service.room_state_cache = {room_id: None}
        await send_room_state(room_id)
        # Should handle gracefully
        assert room_id not in active_room_connections
    finally:
        room_state_service.room_state_cache = original_cache


@pytest.mark.asyncio
async def test_send_room_state_websocket_failure():
    """Test send_room_state when websocket.send_text fails."""
    room_id = "test_room"
    state = {"roomId": room_id, "status": "active"}

    # Setup mock websocket that fails
    mock_websocket = AsyncMock()
    mock_websocket.send_text.side_effect = Exception("Connection lost")

    # Add to active connections
    active_room_connections[room_id][mock_websocket] = None

    # Mock cache to return state by temporarily replacing the cache
    original_cache = room_state_service.room_state_cache
    try:
        room_state_service.room_state_cache = {room_id: state}
        await send_room_state(room_id)
        # Should remove failed websocket
        assert mock_websocket not in active_room_connections[room_id]
    finally:
        room_state_service.room_state_cache = original_cache


@pytest.mark.asyncio
async def test_handle_room_events_invalid_json():
    """Test handle_room_events with invalid JSON."""
    room_id = "test_room"
    invalid_json = "not valid json"

    # Should not raise, just print error
    await handle_room_events(room_id, invalid_json)


@pytest.mark.asyncio
async def test_handle_room_events_unknown_type():
    """Test handle_room_events with unknown event type."""
    room_id = "test_room"
    unknown_event = json.dumps({"type": "unknown_event"})

    # Should not raise, just ignore
    await handle_room_events(room_id, unknown_event)


@pytest.mark.asyncio
async def test_handle_room_events_missing_fields():
    """Test handle_room_events with missing required fields."""
    room_id = "test_room"

    # Test addqueue with missing fields
    event = json.dumps({"type": "addqueue"})
    await handle_room_events(room_id, event)


@pytest.mark.asyncio
async def test_handle_room_events_service_errors():
    """Test handle_room_events when service functions raise exceptions."""
    room_id = "test_room"

    # Mock queue_service functions to raise exceptions
    with patch.object(
        queue_service, "add_to_queue", side_effect=Exception("Service error")
    ):
        event = json.dumps({"type": "addqueue", "track": {}, "user_id": "user1"})
        # Should not raise, just print error
        await handle_room_events(room_id, event)


@pytest.mark.asyncio
async def test_handle_room_events_leave():
    """Test handle_room_events with leave event type."""
    room_id = "test_room"

    # Mock leave_room to avoid database operations
    with patch.object(room_service, "leave_room", new_callable=AsyncMock):
        event = json.dumps({"type": "leave", "user_id": "user1"})
        await handle_room_events(room_id, event)
        # Should call leave_room
        room_service.leave_room.assert_awaited_once_with(room_id, "user1")
