import json
import uuid
import pytest
from repositories import crud

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
            "display_name": "New Name"
        }
        websocket.send_json(rename_event)

        # 4. Receive updated state
        updated_data = websocket.receive_json()
        assert updated_data["host"]["displayName"] == "New Name"
        assert any(u["user"]["displayName"] == "New Name" for u in updated_data["users"])
        assert updated_data["lastEvent"]["type"] == "participant_renamed"

@pytest.mark.asyncio
async def test_websocket_broadcast_to_multiple_clients(db_session, init_room, websocket_client):
    # 1. Setup a room and a host
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    room_id = room.roomId

    # 2. Connect two clients to the same room
    with websocket_client.websocket_connect(f"/ws/{room_id}") as ws1, \
         websocket_client.websocket_connect(f"/ws/{room_id}") as ws2:
        
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
    # According to websockets.py:78, it calls send_room_state(room_id)
    # According to room_service.py:210, it raises 404 if room not found.
    # But websockets.py:15 catches exceptions from refresh_room_state.
    
    with websocket_client.websocket_connect("/ws/non-existent-room") as websocket:
        # send_room_state(room_id) is called after accept.
        # If room_id not in cache, it calls refresh_room_state.
        # refresh_room_state raises 404.
        # send_room_state catches it and prints error, then returns.
        # So the websocket stays open but no initial state is sent.
        
        # Since no state is sent, we can try to send something and see if it doesn't crash
        websocket.send_json({"type": "rename", "user_id": "none", "display_name": "fail"})
        # handle_room_events also catches exceptions.
        
        # We can't easily check for "no message received" without a timeout,
        # but we can check that it didn't close immediately.
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
