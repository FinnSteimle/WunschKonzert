import uuid

import pytest

from repositories import track_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_track(db_session):
    """Test creating a new track"""
    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:123",
        "title": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 180,
        "coverUrl": "https://example.com/cover.jpg",
        "deepLink": "https://open.spotify.com/track/123",
    }

    track = await track_repo.create_track(track_data)

    assert track.trackId == track_id
    assert track.title == "Test Song"
    assert track.artist == "Test Artist"
    assert track.duration == 180


@pytest.mark.asyncio
async def test_get_track(db_session):
    """Test retrieving a track by ID"""
    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:456",
        "title": "Another Song",
        "artist": "Another Artist",
    }

    await track_repo.create_track(track_data)
    retrieved_track = await track_repo.get_track(track_id)

    assert retrieved_track is not None
    assert retrieved_track.trackId == track_id
    assert retrieved_track.title == "Another Song"


@pytest.mark.asyncio
async def test_get_track_not_found(db_session):
    """Test retrieving a non-existent track returns None"""
    non_existent_id = str(uuid.uuid4())
    track = await track_repo.get_track(non_existent_id)
    assert track is None
