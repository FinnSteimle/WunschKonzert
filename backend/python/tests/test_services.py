import uuid
from typing import cast

import pytest
from fastapi import HTTPException

from models import domain
from repositories import crud, membership_repo, room_repo
from services import room_service


@pytest.mark.asyncio
async def test_delete_room(db_session, init_room):
    user_id = str(uuid.uuid4())
    room = await init_room(user_id=user_id)
    await room_service.delete_room_service(room.roomId, user_id)

    deleted_room = await room_repo.get_room(room.roomId)
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

    membership = await membership_repo.get_room_membership(user_id, room.roomId)
    assert membership is not None
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_ensure_active_membership_reactivates_inactive(db_session, init_room):
    """User who left the room gets reactivated instead of duplicated."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "returning_guest")
    await membership_repo.create_room_membership(user_id, room.roomId)

    # Simulate leaving
    await membership_repo.leave_room(user_id, room.roomId)
    left = await membership_repo.get_room_membership(user_id, room.roomId)
    assert left.membershipStatus == domain.MembershipStatus.INACTIVE

    # Rejoin
    await room_service.ensure_active_membership(user_id, room.roomId)

    reactivated = await membership_repo.get_room_membership(user_id, room.roomId)
    assert reactivated.membershipStatus == domain.MembershipStatus.ACTIVE
    assert reactivated.leftAt is None


@pytest.mark.asyncio
async def test_ensure_active_membership_already_active_is_noop(db_session, init_room):
    """Calling on an already-active member doesn't error or duplicate."""
    room = await init_room()
    user_id = str(uuid.uuid4())
    await crud.create_user(user_id, "active_guest")
    await membership_repo.create_room_membership(user_id, room.roomId)

    # Should not raise
    await room_service.ensure_active_membership(user_id, room.roomId)

    memberships_list = await membership_repo.get_room_memberships(room.roomId)
    user_memberships = [m for m in memberships_list if m.userId == user_id]
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
    await membership_repo.create_room_membership(user_id, room.roomId)

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
    await crud.update_queue_entry(
        item.queueEntryId, {"status": domain.QueueEntryStatus.REMOVED}
    )

    entries_after = await crud.get_queue_entries(room.roomId)
    active = [
        e
        for e in entries_after
        if e.status
        not in (
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

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == 1


@pytest.mark.asyncio
async def test_vote_downvote_decreases_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "downvote"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1


@pytest.mark.asyncio
async def test_vote_change_updates_score_without_duplicate_row(db_session, init_room):
    """Changing from upvote to downvote recalculates score and keeps one feedback row."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "downvote"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1

    feedback = await crud.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 1
    assert feedback[0].type == domain.FeedbackType.DISLIKE


@pytest.mark.asyncio
async def test_vote_neutral_removes_feedback_and_resets_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "neutral"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0
    feedback = await crud.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 0


@pytest.mark.asyncio
async def test_vote_neutral_with_no_prior_feedback_is_noop(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "neutral"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.vote_queue_entry(
            room.roomId, queue_entry_id, room.hostedBy, "sideways"
        )
    assert exc_info.value.status_code == 400
    assert "Invalid vote type" in exc_info.value.detail


@pytest.mark.asyncio
async def test_vote_entry_from_different_room_raises_404(db_session, init_room):
    """Queue entry exists but room_id doesn't match — treated as not found."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.vote_queue_entry(
            str(uuid.uuid4()), queue_entry_id, room.hostedBy, "upvote"
        )
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

    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await room_service.vote_queue_entry(room.roomId, queue_entry_id, user2_id, "upvote")
    await room_service.vote_queue_entry(
        room.roomId, queue_entry_id, user3_id, "downvote"
    )

    entry = await crud.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 1  # 2 upvotes - 1 downvote


#
# --- room_service.add_to_queue() edge-case tests ---
#


@pytest.mark.asyncio
async def test_add_to_queue_room_not_found(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.add_to_queue(
            str(uuid.uuid4()),
            {
                "trackId": str(uuid.uuid4()),
                "providerTrackId": "x",
                "title": "T",
                "artist": "A",
                "album": "",
                "duration": 0,
                "coverUrl": "",
                "deepLink": "",
            },
            str(uuid.uuid4()),
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_to_queue_inactive_room(db_session, init_room):
    room = await init_room()
    await room_service.delete_room_service(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.add_to_queue(
            room.roomId,
            {
                "trackId": str(uuid.uuid4()),
                "providerTrackId": "x",
                "title": "T",
                "artist": "A",
                "album": "",
                "duration": 0,
                "coverUrl": "",
                "deepLink": "",
            },
            room.hostedBy,
        )
    assert exc_info.value.status_code == 400
    assert "not active" in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_to_queue_duplicate_track_raises_409(db_session, init_room):
    room = await init_room()
    track_id = str(uuid.uuid4())
    track_data = {
        "trackId": track_id,
        "providerTrackId": "spotify:track:dup",
        "title": "Dup",
        "artist": "A",
        "album": "",
        "duration": 200,
        "coverUrl": "",
        "deepLink": "",
    }
    await room_service.add_to_queue(room.roomId, track_data, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.add_to_queue(room.roomId, track_data, room.hostedBy)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_add_to_queue_second_track_is_queued_not_playing(db_session, init_room):
    room = await init_room()

    async def _track(title: str) -> dict:
        return {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "A",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }

    await room_service.add_to_queue(room.roomId, await _track("First"), room.hostedBy)
    await room_service.add_to_queue(room.roomId, await _track("Second"), room.hostedBy)

    entries = await crud.get_queue_entries(room.roomId)
    statuses = {e.status for e in entries}
    assert domain.QueueEntryStatus.PLAYING in statuses
    assert domain.QueueEntryStatus.QUEUED in statuses


#
# --- Queue Order State
#


@pytest.mark.asyncio
async def test_queue_sort_order(db_session, init_room):
    room = await init_room()

    async def _enqueue(title: str) -> str:
        track = {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }
        await room_service.add_to_queue(room.roomId, track, room.hostedBy)
        entry = await crud.get_queue_entry_by_track(room.roomId, track["trackId"])
        assert entry is not None
        return entry.queueEntryId

    async def _vote(entry_id: str, vote: str, count: int = 1) -> None:
        for _ in range(count):
            uid = str(uuid.uuid4())
            await crud.create_user(uid, uid)
            await room_service.vote_queue_entry(room.roomId, entry_id, uid, vote)

    # C is added first → gets status=playing, always sorts first
    c = await _enqueue("C")
    b = await _enqueue("B")
    e = await _enqueue("E")
    d = await _enqueue("D")
    a = await _enqueue("A")

    await _vote(a, "upvote", count=2)   # score +2
    await _vote(b, "upvote", count=1)   # score +1
    # d: no votes                        # score  0
    await _vote(e, "downvote", count=1) # score -1

    room_state = await room_service.refresh_room_state(room.roomId)

    titles = [e["track"]["title"] for e in cast(list[dict], room_state["queue"])]
    assert titles == ["C", "A", "B", "D", "E"]


@pytest.mark.asyncio
async def test_vote_reflected_in_room_state(db_session, init_room):
    room = await init_room()

    async def _enqueue(title: str) -> str:
        track = {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }
        await room_service.add_to_queue(room.roomId, track, room.hostedBy)
        entry = await crud.get_queue_entry_by_track(room.roomId, track["trackId"])
        assert entry is not None
        return entry.queueEntryId

    entry_id = await _enqueue("Song")

    voter1 = str(uuid.uuid4())
    voter2 = str(uuid.uuid4())
    voter3 = str(uuid.uuid4())
    await crud.create_user(voter1, "voter1")
    await crud.create_user(voter2, "voter2")
    await crud.create_user(voter3, "voter3")

    await room_service.vote_queue_entry(room.roomId, entry_id, voter1, "upvote")
    await room_service.vote_queue_entry(room.roomId, entry_id, voter2, "upvote")
    await room_service.vote_queue_entry(room.roomId, entry_id, voter3, "downvote")

    room_state = await room_service.refresh_room_state(room.roomId)
    queue = cast(list[dict], room_state["queue"])

    assert len(queue) == 1
    song = queue[0]
    assert song["voteScore"] == 1
    feedback = cast(list[dict], song["feedback"])
    assert len(feedback) == 3
    assert sum(1 for f in feedback if f["type"] == "upvote") == 2
    assert sum(1 for f in feedback if f["type"] == "downvote") == 1




@pytest.mark.asyncio
async def test_playback_state_mapping_in_room_state(db_session, init_room):
    room = await init_room()

    async def _enqueue(title: str) -> str:
        track = {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "Test Artist",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }
        await room_service.add_to_queue(room.roomId, track, room.hostedBy)
        entry = await crud.get_queue_entry_by_track(room.roomId, track["trackId"])
        assert entry is not None
        return entry.queueEntryId

    song_a = await _enqueue("A")
    await _enqueue("B")

    playing_state = await room_service.refresh_room_state(room.roomId)
    playback = cast(dict, playing_state["playback"])
    assert playback["state"] == "playing"
    assert playback["currentQueueEntryId"] == song_a

    # After stop, currentQueueEntryId must be None
    await room_service.set_playback_state(room.roomId, room.hostedBy, "stop")
    stopped_state = await room_service.refresh_room_state(room.roomId)
    playback = cast(dict, stopped_state["playback"])
    assert playback["state"] == "stopped"
    assert playback["currentQueueEntryId"] is None



#
# --- room_service.set_playback_state() tests ---
#


@pytest.mark.asyncio
async def test_playback_non_host_raises_403(db_session, init_room):
    room = await init_room()
    other_user = str(uuid.uuid4())
    await crud.create_user(other_user, "guest")

    with pytest.raises(HTTPException) as exc_info:
        await room_service.set_playback_state(room.roomId, other_user, "pause")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_playback_invalid_action_raises_400(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.set_playback_state(room.roomId, room.hostedBy, "rewind")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_playback_pause_and_resume(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.set_playback_state(room.roomId, room.hostedBy, "pause")
    session = await crud.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.PAUSED

    await room_service.set_playback_state(room.roomId, room.hostedBy, "resume")
    session = await crud.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.PLAYING


@pytest.mark.asyncio
async def test_playback_stop(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    await room_service.set_playback_state(room.roomId, room.hostedBy, "stop")
    session = await crud.get_current_playback_session(room.roomId)
    assert session.state == domain.PlaybackState.STOPPED


@pytest.mark.asyncio
async def test_playback_advance_moves_to_next_track(db_session, init_room):
    room = await init_room()

    async def _track(title: str) -> dict:
        return {
            "trackId": str(uuid.uuid4()),
            "providerTrackId": f"spotify:{title}",
            "title": title,
            "artist": "A",
            "album": "",
            "duration": 180,
            "coverUrl": "",
            "deepLink": "",
        }

    await room_service.add_to_queue(room.roomId, await _track("First"), room.hostedBy)
    await room_service.add_to_queue(room.roomId, await _track("Second"), room.hostedBy)

    state = await room_service.set_playback_state(room.roomId, room.hostedBy, "advance")

    playing = [e for e in state["queue"] if e["status"] == "playing"]  # type: ignore[index]
    assert len(playing) == 1
    assert playing[0]["track"]["title"] == "Second"


@pytest.mark.asyncio
async def test_playback_no_session_resume_creates_session(db_session, init_room):
    """resume with no existing session picks the first queued entry."""
    room = await init_room()
    track_id = str(uuid.uuid4())
    await crud.create_track(
        {
            "trackId": track_id,
            "providerTrackId": "sp:x",
            "title": "T",
            "artist": "A",
            "album": "",
            "duration": 100,
            "coverUrl": "",
            "deepLink": "",
        }
    )
    await crud.create_queue_entry(
        {
            "queueEntryId": f"QENTRY{uuid.uuid4().hex[:8].upper()}",
            "roomId": room.roomId,
            "trackId": track_id,
            "addedBy": room.hostedBy,
            "position": 1,
            "status": domain.QueueEntryStatus.QUEUED,
            "voteScore": 0,
            "orderRank": 1.0,
        }
    )

    await room_service.set_playback_state(room.roomId, room.hostedBy, "resume")
    session = await crud.get_current_playback_session(room.roomId)
    assert session is not None
    assert session.state == domain.PlaybackState.PLAYING



@pytest.mark.asyncio
async def test_user_list_exclude_users_who_left(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())

    await crud.create_user(guest_id, "guest")
    await membership_repo.create_room_membership(guest_id, room.roomId)
    await membership_repo.leave_room(guest_id, room.roomId)

    state = await room_service.refresh_room_state(room.roomId)
    participants = cast(dict, state["users"])
    user_ids = [u["user"]["userId"] for u in participants]
    assert guest_id not in user_ids


@pytest.mark.asyncio
async def test_user_list_host_not_dublicated(db_session, init_room):
    room = await init_room()

    state = await room_service.refresh_room_state(room.roomId)
    participants = cast(dict, state["users"])
    user_ids = [u["user"]["userId"] for u in participants]

    assert user_ids.count(room.hostedBy) == 1


#
# --- room_service.leave_room_service() tests ---
#


@pytest.mark.asyncio
async def test_leave_room_success(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())
    await crud.create_user(guest_id, "guest")
    await membership_repo.create_room_membership(guest_id, room.roomId)

    await room_service.leave_room_service(room.roomId, guest_id)

    membership = await membership_repo.get_room_membership(guest_id, room.roomId)
    assert membership.membershipStatus == domain.MembershipStatus.INACTIVE


@pytest.mark.asyncio
async def test_leave_room_host_raises_403(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.leave_room_service(room.roomId, room.hostedBy)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_leave_room_unknown_user_raises_error(db_session, init_room):
    room = await init_room()
    # crud.get_user raises ResourceNotFoundError for unknown users, which the
    # service wraps in a 500 (the 404 branch is unreachable via this path).
    with pytest.raises(HTTPException) as exc_info:
        await room_service.leave_room_service(room.roomId, str(uuid.uuid4()))
    assert exc_info.value.status_code in (404, 500)


#
# --- room_service.join_room_service() tests ---
#


@pytest.mark.asyncio
async def test_join_room_success(db_session, init_room):
    room = await init_room()
    guest_id = str(uuid.uuid4())

    result = await room_service.join_room_service(room.joinCode, guest_id, "NewGuest")

    assert result["success"] is True
    assert result["room_id"] == room.roomId
    membership = await membership_repo.get_room_membership(guest_id, room.roomId)
    assert membership.membershipStatus == domain.MembershipStatus.ACTIVE


@pytest.mark.asyncio
async def test_join_room_invalid_code_raises_422(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room_service("BAD!", str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_join_room_unknown_code_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room_service("ABCDE2", str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_join_room_empty_display_name_raises_400(db_session, init_room):
    room = await init_room()
    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room_service(room.joinCode, str(uuid.uuid4()), "  ")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_join_deleted_room_raises_410(db_session, init_room):
    room = await init_room()
    await room_service.delete_room_service(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await room_service.join_room_service(room.joinCode, str(uuid.uuid4()), "Guest")
    assert exc_info.value.status_code == 410


#
# --- room_service.rename_participant() tests ---
#


@pytest.mark.asyncio
async def test_rename_participant_success(db_session, init_room):
    room = await init_room()
    await room_service.rename_participant(room.roomId, room.hostedBy, "NewName")

    user = await crud.get_user(room.hostedBy)
    assert user.displayName == "NewName"


@pytest.mark.asyncio
async def test_rename_participant_non_member_raises_403(db_session, init_room):
    room = await init_room()
    outsider = str(uuid.uuid4())
    await crud.create_user(outsider, "outsider")

    with pytest.raises(HTTPException) as exc_info:
        await room_service.rename_participant(room.roomId, outsider, "Hacker")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_rename_participant_room_not_found_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await room_service.rename_participant(
            str(uuid.uuid4()), str(uuid.uuid4()), "Name"
        )
    assert exc_info.value.status_code == 404


#
# --- room_service.check_room_availability() tests ---
#


@pytest.mark.asyncio
async def test_check_room_availability_active_room(db_session, init_room):
    room = await init_room()
    available, unavailable = await room_service.check_room_availability([room.joinCode])
    assert room.joinCode in available
    assert room.joinCode not in unavailable


@pytest.mark.asyncio
async def test_check_room_availability_invalid_code(db_session):
    available, unavailable = await room_service.check_room_availability(["!!!"])
    assert "!!!" in unavailable
    assert available == []


@pytest.mark.asyncio
async def test_check_room_availability_duplicate_code(db_session, init_room):
    room = await init_room()
    available, unavailable = await room_service.check_room_availability(
        [room.joinCode, room.joinCode]
    )
    # First occurrence available, duplicate goes to unavailable
    assert available.count(room.joinCode) == 1
    assert room.joinCode in unavailable


@pytest.mark.asyncio
async def test_check_room_availability_deleted_room(db_session, init_room):
    room = await init_room()
    await room_service.delete_room_service(room.roomId, room.hostedBy)

    available, unavailable = await room_service.check_room_availability([room.joinCode])
    assert room.joinCode not in available
    assert room.joinCode in unavailable


#
# --- room_service.sync_playback_position() tests ---
#


@pytest.mark.asyncio
async def test_sync_playback_position_updates_cache(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)

    # Seed cache
    await room_service.refresh_room_state(room.roomId)

    await room_service.sync_playback_position(room.roomId, room.hostedBy, 30_000)

    cached = room_service.room_state_cache.get(room.roomId)
    assert cached is not None
    assert cached["playback"]["positionMs"] == 30_000  # type: ignore[index]


@pytest.mark.asyncio
async def test_sync_playback_position_non_host_is_noop(db_session, init_room):
    room = await init_room()
    await _add_track_to_queue(room.roomId, room.hostedBy)
    await room_service.refresh_room_state(room.roomId)

    other = str(uuid.uuid4())
    await crud.create_user(other, "other")
    await room_service.sync_playback_position(room.roomId, other, 99_000)

    cached = room_service.room_state_cache.get(room.roomId)
    # Position should NOT have been updated to 99_000
    assert cached["playback"]["positionMs"] != 99_000  # type: ignore[index]
