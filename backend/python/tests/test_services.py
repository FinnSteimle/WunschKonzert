import uuid

import pytest
from fastapi import HTTPException

from models import domain
from repositories import crud
from services import room_service


@pytest.mark.asyncio
async def test_delete_room(db_session, init_room):
    user_id = str(uuid.uuid4())
    room = await init_room(user_id=user_id)
    await room_service.delete_room_service(room.roomId, user_id)

    deleted_room = await crud.get_room(room.roomId)
    assert deleted_room.status == domain.RoomStatus.DELETED


#
# --- room_service.ensure_user_display_name() tests ---
#
@pytest.mark.asyncio
async def test_user_display_name_at_max_length(db_session):
    user_name = "a" * 60
    await room_service.ensure_user_display_name(str(uuid.uuid4()), user_name)
    # no exception → pass

@pytest.mark.asyncio
async def test_user_display_name_above_max_length(db_session):
    user_name = "a" * 61
    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_user_display_name(str(uuid.uuid4()), user_name)
    assert exc_info.value.status_code == 400
    assert "too long" in exc_info.value.detail

@pytest.mark.asyncio
async def test_user_display_name_empty_raises(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_user_display_name(str(uuid.uuid4()), "   ")
    assert exc_info.value.status_code == 400
    assert "required" in exc_info.value.detail

@pytest.mark.asyncio
async def test_user_display_name_strips_whitespace(db_session):
    user_id = str(uuid.uuid4())
    await room_service.ensure_user_display_name(user_id, "  Alice  ")
    user = await crud.get_user(user_id)
    assert user.displayName == "Alice"


#
# --- room_service.ensure_provider_exists() tests ---
#
@pytest.mark.asyncio
async def test_ensure_provider_exists_with_seeded_provider(db_session):
    provider_id = str(uuid.uuid4())
    await crud.create_music_provider(provider_id, "Spotify")

    # Should not raise
    await room_service.ensure_provider_exists(provider_id)


@pytest.mark.asyncio
async def test_ensure_provider_exists_with_unknown_provider(db_session):
    fake_id = str(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await room_service.ensure_provider_exists(fake_id)
    assert exc_info.value.status_code == 400
    assert "Unsupported music provider" in exc_info.value.detail


#
# --- room_service.ensure_active_membership() tests ---
#
@pytest.mark.asyncio
async def test_ensure_active_membership_creates_new(db_session, init_room):
    """User with no prior membership gets one created."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "new_guest")

    await room_service.ensure_active_membership(user_id, room.roomId)

    membership = await crud.get_room_membership(user_id, room.roomId)
    assert membership is not None
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_ensure_active_membership_reactivates_inactive(db_session, init_room):
    """User who left the room gets reactivated instead of duplicated."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "returning_guest")
    await crud.create_room_membership(user_id, room.roomId)

    # Simulate leaving
    await crud.leave_room(user_id, room.roomId)
    left = await crud.get_room_membership(user_id, room.roomId)
    assert left.membershipStatus == domain.MembershipStatus.INACTIVE

    # Rejoin
    await room_service.ensure_active_membership(user_id, room.roomId)

    reactivated = await crud.get_room_membership(user_id, room.roomId)
    assert reactivated.membershipStatus == domain.MembershipStatus.ACTIVE
    assert reactivated.leftAt is None


@pytest.mark.asyncio
async def test_ensure_active_membership_already_active_is_noop(db_session, init_room):
    """Calling on an already-active member doesn't error or duplicate."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "active_guest")
    await crud.create_room_membership(user_id, room.roomId)

    # Should not raise
    await room_service.ensure_active_membership(user_id, room.roomId)

    memberships = await crud.get_room_memberships(room.roomId)
    user_memberships = [m for m in memberships if m.userId == user_id]
    assert len(user_memberships) == 1
    assert user_memberships[0].membershipStatus == domain.MembershipStatus.ACTIVE



#
# --- Queue Unit Tests ---
#

@pytest.mark.asyncio
async def test_queue_add_remove(db_session, init_room):
    """Test adding and removing items from the queue."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "queue_guest")
    await crud.create_room_membership(user_id, room.roomId)

    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:test123",
        "title": "Fireworks",
        "artist": "Katy Perry",
        "album": "Teenage Dream",
        "duration": 228,
        "coverUrl": "",
        "deepLink": "",
    }

    # Add a track to the queue
    await room_service.add_to_queue(room.roomId, track_data, user_id)

    entries = await crud.get_queue_entries(room.roomId)
    assert len(entries) == 1
    item = entries[0]
    assert item.trackId == track_id
    assert item.addedBy == user_id
    assert item.position == 1
    assert item.status == domain.QueueEntryStatus.PLAYING

    # Remove the item from the queue (entries are marked REMOVED, not hard-deleted)
    await crud.update_queue_entry(item.queueEntryId, {"status": domain.QueueEntryStatus.REMOVED})

    entries_after = await crud.get_queue_entries(room.roomId)
    active = [
        e for e in entries_after
        if e.status not in (
            domain.QueueEntryStatus.REMOVED,
            domain.QueueEntryStatus.PLAYED,
            domain.QueueEntryStatus.SKIPPED,
        )
    ]
    assert len(active) == 0


#
# --- room_service.vote_queue_entry() tests ---
#

async def _add_track_to_queue(room_id: str, user_id: str) -> str:
    """Helper: add one track to a room, return its queueEntryId."""
    track_id = str(uuid.uuid4())
    await room_service.add_to_queue(
        room_id,
        {
            "trackId": track_id,
            "providerTrackId": f"spotify:track:{track_id[:8]}",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        },
        user_id,
    )
    entries = await crud.get_queue_entries(room_id)
    return entries[0].queueEntryId


@pytest.mark.asyncio
async def test_vote_upvote_increases_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "upvote")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == 1


@pytest.mark.asyncio
async def test_vote_downvote_decreases_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "downvote")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1


@pytest.mark.asyncio
async def test_vote_change_updates_score_without_duplicate_row(db_session, init_room):
    """Changing from upvote to downvote recalculates score and keeps one feedback row."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "upvote")
    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "downvote")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1

    feedback = await crud.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 1
    assert feedback[0].type == domain.FeedbackType.DISLIKE


@pytest.mark.asyncio
async def test_vote_neutral_removes_feedback_and_resets_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "upvote")
    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "neutral")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0
    feedback = await crud.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 0


@pytest.mark.asyncio
async def test_vote_neutral_with_no_prior_feedback_is_noop(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "neutral")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "sideways")
    assert exc_info.value.status_code == 400
    assert "Invalid vote type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_vote_entry_from_different_room_raises_404(db_session, init_room):
    """Queue entry exists but room_id doesn't match — treated as not found."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.vote_queue_entry(str(uuid.uuid4()), queue_entry_id, room.hostedBy, "upvote")
    assert exc_info.value.status_code == 404
    assert "Queue entry not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_vote_multiple_users_score_aggregated(db_session, init_room):
    """Two upvotes and one downvote from different users produce score of 1."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    user2_id = str(uuid.uuid4())
    user3_id = str(uuid.uuid4())
    await crud.create_user(user2_id, "voter2")
    await crud.create_user(user3_id, "voter3")

    await room_service.vote_queue_entry(room.roomId, queue_entry_id, room.hostedBy, "upvote")
    await room_service.vote_queue_entry(room.roomId, queue_entry_id, user2_id, "upvote")
    await room_service.vote_queue_entry(room.roomId, queue_entry_id, user3_id, "downvote")

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 1  # 2 upvotes - 1 downvote

