import uuid

import pytest

from models.domain import FeedbackType, QueueEntryStatus
from repositories import queue_entry_repo, song_feedback_repo, track_repo, user_repo

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_song_feedback(db_session, init_room):
    """Test creating song feedback"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
            "status": QueueEntryStatus.PLAYING,
        }
    )

    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "test_user")

    feedback_data = {
        "queueEntryId": queue_entry_id,
        "userId": user_id,
        "type": FeedbackType.LIKE,
    }

    feedback = await song_feedback_repo.create_or_update_song_feedback(feedback_data)

    assert feedback.queueEntryId == queue_entry_id
    assert feedback.userId == user_id
    assert feedback.type == FeedbackType.LIKE


@pytest.mark.asyncio
async def test_update_song_feedback(db_session, init_room):
    """Test updating existing song feedback"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
        }
    )

    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "test_user")

    # Create initial feedback
    await song_feedback_repo.create_or_update_song_feedback(
        {
            "queueEntryId": queue_entry_id,
            "userId": user_id,
            "type": FeedbackType.LIKE,
        }
    )

    # Update to dislike
    updated_feedback = await song_feedback_repo.create_or_update_song_feedback(
        {
            "queueEntryId": queue_entry_id,
            "userId": user_id,
            "type": FeedbackType.DISLIKE,
        }
    )

    assert updated_feedback.type == FeedbackType.DISLIKE


@pytest.mark.asyncio
async def test_get_song_feedback_by_queue_entry(db_session, init_room):
    """Test retrieving all feedback for a queue entry"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
        }
    )

    # Create feedback from multiple users
    for i in range(3):
        user_id = str(uuid.uuid4())
        await user_repo.create_user(user_id, f"user_{i}")
        await song_feedback_repo.create_or_update_song_feedback(
            {
                "queueEntryId": queue_entry_id,
                "userId": user_id,
                "type": FeedbackType.LIKE,
            }
        )

    feedback_list = await song_feedback_repo.get_song_feedback_by_queue_entry(
        queue_entry_id
    )
    assert len(feedback_list) == 3


@pytest.mark.asyncio
async def test_delete_song_feedback(db_session, init_room):
    """Test deleting song feedback"""
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)

    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "spotify:track:123",
            "title": "Test Song",
            "artist": "Test Artist",
        }
    )

    queue_entry_id = str(uuid.uuid4())
    await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": queue_entry_id,
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": host_id,
            "position": 1,
        }
    )

    user_id = str(uuid.uuid4())
    await user_repo.create_user(user_id, "test_user")

    await song_feedback_repo.create_or_update_song_feedback(
        {
            "queueEntryId": queue_entry_id,
            "userId": user_id,
            "type": FeedbackType.LIKE,
        }
    )

    await song_feedback_repo.delete_song_feedback(queue_entry_id, user_id)

    feedback = await song_feedback_repo.get_song_feedback(queue_entry_id, user_id)
    assert feedback is None
