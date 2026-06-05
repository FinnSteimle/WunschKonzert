import uuid
from typing import cast

import pytest
from fastapi import HTTPException

from models import domain
from repositories import (
    membership_repo,
    queue_entry_repo,
    song_feedback_repo,
    user_repo,
)
from services import queue_service, room_state_service, vote_service

pytestmark = pytest.mark.integration


async def _add_track_to_queue(room_id: str, user_id: str) -> str:
    """Helper: add one track to a room, return its queueEntryId."""
    track_id = str(uuid.uuid4())
    await queue_service.add_to_queue(
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
    entries = await queue_entry_repo.get_queue_entries(room_id)
    return entries[0].queueEntryId


@pytest.mark.asyncio
async def test_vote_upvote_increases_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry.voteScore == 1


@pytest.mark.asyncio
async def test_vote_downvote_decreases_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "downvote"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1


@pytest.mark.asyncio
async def test_vote_change_updates_score_without_duplicate_row(db_session, init_room):
    """Changing from upvote to downvote recalculates score and keeps one feedback row."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "downvote"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry.voteScore == -1

    feedback = await song_feedback_repo.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 1
    assert feedback[0].type == domain.FeedbackType.DISLIKE


@pytest.mark.asyncio
async def test_vote_neutral_removes_feedback_and_resets_score(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "neutral"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0
    feedback = await song_feedback_repo.get_song_feedback_by_queue_entry(queue_entry_id)
    assert len(feedback) == 0


@pytest.mark.asyncio
async def test_vote_neutral_with_no_prior_feedback_is_noop(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "neutral"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry is not None
    assert entry.voteScore == 0


@pytest.mark.asyncio
async def test_vote_invalid_type_raises_400(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await vote_service.vote_queue_entry(
            room.roomId, queue_entry_id, room.hostedBy, "sideways"
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_vote_entry_from_different_room_raises_404(db_session, init_room):
    """Queue entry exists but room_id doesn't match; treated as not found."""
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    with pytest.raises(HTTPException) as exc_info:
        await vote_service.vote_queue_entry(
            str(uuid.uuid4()), queue_entry_id, room.hostedBy, "upvote"
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_vote_multiple_users_score_aggregated(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    user2_id = str(uuid.uuid4())
    user3_id = str(uuid.uuid4())
    await user_repo.create_user(user2_id, "voter2")
    await user_repo.create_user(user3_id, "voter3")

    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, room.hostedBy, "upvote"
    )
    await vote_service.vote_queue_entry(room.roomId, queue_entry_id, user2_id, "upvote")
    await vote_service.vote_queue_entry(
        room.roomId, queue_entry_id, user3_id, "downvote"
    )

    entry = await queue_entry_repo.get_queue_entry(queue_entry_id)
    assert entry.voteScore == 1


@pytest.mark.asyncio
async def test_vote_reflected_in_room_state(db_session, init_room):
    room = await init_room()
    queue_entry_id = await _add_track_to_queue(room.roomId, room.hostedBy)

    voter1 = str(uuid.uuid4())
    await user_repo.create_user(voter1, "voter1")

    await vote_service.vote_queue_entry(room.roomId, queue_entry_id, voter1, "upvote")

    room_state = await room_state_service.refresh_room_state(room.roomId)
    song = cast(list[dict], room_state["queue"])[0]
    assert song["voteScore"] == 1
    assert any(f["type"] == "upvote" for f in song["feedback"])


@pytest.mark.asyncio
async def test_vote_replay_refreshes_room_state(db_session, init_room):
    room = await init_room()

    guest_id = str(uuid.uuid4())
    await user_repo.create_user(guest_id, "guest")
    await membership_repo.create_room_membership(guest_id, room.roomId)

    track = {
        "trackId": str(uuid.uuid4()),
        "providerTrackId": "spotify:track:replay",
        "title": "Replay Song",
        "artist": "Artist",
        "album": "",
        "duration": 180,
        "coverUrl": "",
        "deepLink": "",
    }
    await queue_service.add_to_queue(room.roomId, track, room.hostedBy)

    entry = await queue_entry_repo.get_queue_entry_by_track(
        room.roomId, track["trackId"]
    )
    assert entry is not None

    first_state = await vote_service.vote_queue_entry(
        room.roomId, entry.queueEntryId, guest_id, "replay"
    )

    assert first_state["lastEvent"]["type"] == "vote_updated"
    assert first_state["lastActivity"]["type"] == "replay_vote"

    second_state = await vote_service.vote_queue_entry(
        room.roomId, entry.queueEntryId, room.hostedBy, "replay"
    )

    assert second_state["lastActivity"]["type"] == "replay_threshold_met"
    queue = cast(list[dict], second_state["queue"])
    assert len(queue) == 2
    original_entry = next(
        item for item in queue if item["queueEntryId"] == entry.queueEntryId
    )
    assert not any(
        feedback["type"] == "replay" for feedback in original_entry["feedback"]
    )
    replay_entry = next(
        item for item in queue if item["status"] == "queued" and item["position"] == 0
    )
    assert replay_entry["track"]["title"] == "Replay Song"
