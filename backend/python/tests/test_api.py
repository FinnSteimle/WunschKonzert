import uuid

import pytest

from repositories import crud
from services.providers.base import ProviderTrack


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_hello_world(client):
    response = await client.get("/hello")
    assert response.status_code == 200
    assert response.json()["message"] == "Hello World"


@pytest.mark.asyncio
async def test_create_room_success(client, db_session):
    # Seed provider
    provider_id = "spotify"
    await crud.create_music_provider(provider_id, "Spotify", db_session)
    await db_session.commit()

    payload = {
        "name": "My Awesome Room",
        "user_id": str(uuid.uuid4()),
        "display_name": "Host User",
        "supported_provider_id": provider_id,
    }
    response = await client.post("/create_room", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "room_id" in data
    assert "join_code" in data
    assert len(data["join_code"]) == 6


@pytest.mark.asyncio
async def test_create_room_invalid_provider(client, db_session):
    payload = {
        "name": "My Awesome Room",
        "user_id": str(uuid.uuid4()),
        "display_name": "Host User",
        "supported_provider_id": "invalid_provider",
    }
    response = await client.post("/create_room", json=payload)
    assert response.status_code == 400
    assert "Unsupported music provider" in response.json()["detail"]


@pytest.mark.asyncio
async def test_join_room_success(client, db_session, init_room):
    room = await init_room()
    user_id = str(uuid.uuid4())

    payload = {
        "join_code": room.joinCode,
        "user_id": user_id,
        "display_name": "Guest User",
    }
    response = await client.post("/join_room", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["room_id"] == room.roomId


@pytest.mark.asyncio
async def test_join_room_not_found(client, db_session):
    payload = {
        "join_code": "ABCDEF",
        "user_id": str(uuid.uuid4()),
        "display_name": "Guest User",
    }
    response = await client.post("/join_room", json=payload)
    assert response.status_code == 404
    assert "Room not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_join_room_invalid_code(client, db_session):
    payload = {
        "join_code": "123",  # too short, invalid characters
        "user_id": str(uuid.uuid4()),
        "display_name": "Guest User",
    }
    response = await client.post("/join_room", json=payload)
    # Based on rooms.py, it raises 422 for invalid join code format
    assert response.status_code == 422
    assert "Join code must be exactly 6 characters" in response.json()["detail"]


@pytest.mark.asyncio
async def test_leave_room_success(client, db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    guest_id = str(uuid.uuid4())
    await crud.create_user(guest_id, "Guest", db_session)
    await db_session.commit()
    await crud.create_room_membership(guest_id, room.roomId)

    payload = {"room_id": room.roomId, "user_id": guest_id}
    response = await client.post("/leave_room", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_delete_room_success(client, db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    payload = {"room_id": room.roomId, "user_id": host_id}
    response = await client.post("/delete_room", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_rooms_availability(client, db_session, init_room):
    room1 = await init_room(provider_id=str(uuid.uuid4()))
    room2 = await init_room(provider_id=str(uuid.uuid4()))

    payload = {"join_codes": [room1.joinCode, room2.joinCode, "ABCDEF", "GHIJKL"]}
    response = await client.post("/rooms/availability", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert room1.joinCode in data["available_join_codes"]
    assert room2.joinCode in data["available_join_codes"]
    assert "ABCDEF" in data["unavailable_join_codes"]
    assert "GHIJKL" in data["unavailable_join_codes"]


@pytest.mark.asyncio
async def test_search_tracks_dispatches_provider(
    client, db_session, init_room, monkeypatch
):
    room = await init_room(provider_id="spotify", provider_name="Spotify")

    class _FakeProvider:
        provider_id = "spotify"

        async def search_tracks(self, query: str) -> list[ProviderTrack]:
            assert query == "fire"
            return [
                ProviderTrack(
                    track_id="track1",
                    provider_track_id="provider-track-1",
                    title="Fire",
                    artist="Artist",
                    album="Album",
                    duration=180,
                    cover_url="https://cover",
                    deep_link="https://link",
                )
            ]

    monkeypatch.setattr(
        "api.routers.provider_search.get_provider_client", lambda _: _FakeProvider()
    )

    response = await client.get(f"/rooms/{room.roomId}/search", params={"q": "fire"})
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "spotify"
    assert data["query"] == "fire"
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["trackId"] == "track1"
    assert data["tracks"][0]["providerTrackId"] == "provider-track-1"


@pytest.mark.asyncio
async def test_search_tracks_unsupported_provider_returns_400(
    client, db_session, init_room
):
    room = await init_room(provider_id="apple", provider_name="Apple Music")

    response = await client.get(f"/rooms/{room.roomId}/search", params={"q": "fire"})
    assert response.status_code == 400
    assert "Unsupported music provider" in response.json()["detail"]
