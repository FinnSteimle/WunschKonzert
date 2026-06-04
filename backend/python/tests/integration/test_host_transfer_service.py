"""Integration tests for the host transfer service.

The provider HTTP layer is mocked; everything below it (repos, DB, room state
cache) is exercised end-to-end against the test postgres.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from models.domain import PlaybackState, QueueEntryStatus
from repositories import (
    membership_repo,
    music_provider_repo,
    playback_session_repo,
    queue_entry_repo,
    room_repo,
    track_repo,
    user_repo,
)
from services import (
    host_transfer_service,
    room_state_service,
)
from services.providers.base import ProviderTrack

pytestmark = pytest.mark.integration


# ----- helpers -----------------------------------------------------------


async def _link_provider(user_id: str, provider_id: str, session) -> None:
    await music_provider_repo.create_or_update_provider_account_tokens(
        user_id=user_id,
        provider_id=provider_id,
        external_user_id=f"ext-{user_id}",
        access_token="access",
        refresh_token="refresh",
        token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        session=session,
    )


async def _add_member(user_id: str, room_id: str, session) -> None:
    await user_repo.create_user(user_id, f"u-{user_id[:6]}", session)
    await membership_repo.create_room_membership(user_id, room_id, session=session)


async def _add_track_and_queue_entry(
    room_id: str, added_by: str, session, title="Song", artist="Artist"
) -> str:
    track_id = str(uuid.uuid4())
    await track_repo.create_track(
        {
            "trackId": track_id,
            "providerTrackId": f"pt-{track_id[:6]}",
            "title": title,
            "artist": artist,
            "album": "A",
            "duration": 200,
        },
        session=session,
    )
    entry = await queue_entry_repo.create_queue_entry(
        {
            "queueEntryId": str(uuid.uuid4()),
            "roomId": room_id,
            "trackId": track_id,
            "addedBy": added_by,
            "position": (
                await queue_entry_repo.get_max_queue_position(room_id, session)
            )
            + 1,
            "status": QueueEntryStatus.QUEUED,
        },
        session=session,
    )
    return entry.queueEntryId


def _fake_match(track_id: str = "remote-id") -> ProviderTrack:
    return ProviderTrack(
        track_id=track_id,
        provider_track_id=track_id,
        title="Song",
        artist="Artist",
        album="A",
        duration=200,
        cover_url="",
        deep_link="",
    )


# ----- initiate_transfer -------------------------------------------------


@pytest.mark.asyncio
async def test_initiate_transfer_happy_path(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )

    transfer = cast(dict, state["transfer"])
    assert transfer["fromUserId"] == host_id
    assert transfer["toUserId"] == invitee_id
    assert transfer["transferId"]
    assert state["lastActivity"]["type"] == "host_transfer_initiated"  # type: ignore[index]
    assert state["lastActivity"]["userId"] == host_id  # type: ignore[index]


@pytest.mark.asyncio
async def test_initiate_transfer_non_host_caller_403(db_session, init_room):
    host_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(other_id, room.roomId, db_session)
    await _add_member(invitee_id, room.roomId, db_session)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.initiate_transfer(room.roomId, other_id, invitee_id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_initiate_transfer_to_self_400(db_session, init_room):
    host_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.initiate_transfer(room.roomId, host_id, host_id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_initiate_transfer_target_not_member_404(db_session, init_room):
    host_id = str(uuid.uuid4())
    stranger_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await user_repo.create_user(stranger_id, "stranger", db_session)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.initiate_transfer(room.roomId, host_id, stranger_id)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_initiate_transfer_when_pending_409(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await db_session.commit()

    await host_transfer_service.initiate_transfer(room.roomId, host_id, invitee_id)
    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.initiate_transfer(room.roomId, host_id, invitee_id)
    assert exc.value.status_code == 409


# ----- reject_transfer ---------------------------------------------------


@pytest.mark.asyncio
async def test_reject_transfer_clears_invite(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    state2 = await host_transfer_service.reject_transfer(
        room.roomId, transfer_id, invitee_id
    )
    assert "transfer" not in state2
    assert state2["lastActivity"]["type"] == "host_transfer_rejected"  # type: ignore[index]
    assert state2["lastActivity"]["userId"] == invitee_id  # type: ignore[index]


@pytest.mark.asyncio
async def test_reject_transfer_wrong_user_403(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    third_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _add_member(third_id, room.roomId, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.reject_transfer(room.roomId, transfer_id, third_id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_reject_transfer_unknown_id_404(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await db_session.commit()

    await host_transfer_service.initiate_transfer(room.roomId, host_id, invitee_id)

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.reject_transfer(
            room.roomId, "not-a-real-id", invitee_id
        )
    assert exc.value.status_code == 404


# ----- accept_transfer ---------------------------------------------------


@pytest.mark.asyncio
async def test_accept_transfer_swaps_host_and_keeps_matched_tracks(
    db_session, init_room
):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _link_provider(invitee_id, room.supportedProviderId, db_session)
    entry_id = await _add_track_and_queue_entry(room.roomId, host_id, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    fake_provider = AsyncMock()
    fake_provider.find_track_for_user.return_value = _fake_match()

    with patch(
        "services.host_transfer_service.get_provider_client",
        return_value=fake_provider,
    ):
        state2 = await host_transfer_service.accept_transfer(
            room.roomId, transfer_id, invitee_id
        )

    # transfer cleared, host swapped, queue entry still present
    assert "transfer" not in state2
    assert state2["lastActivity"]["type"] == "host_transfer_completed"  # type: ignore[index]
    assert state2["lastActivity"]["userId"] == invitee_id  # type: ignore[index]
    refreshed = await room_repo.get_room(room.roomId)
    assert refreshed.hostedBy == invitee_id

    entry = await queue_entry_repo.get_queue_entry(entry_id)
    assert entry is not None
    assert entry.status == QueueEntryStatus.QUEUED


@pytest.mark.asyncio
async def test_accept_transfer_removes_unmatched_and_pushes_system_message(
    db_session, init_room
):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _link_provider(invitee_id, room.supportedProviderId, db_session)
    entry_id = await _add_track_and_queue_entry(room.roomId, host_id, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    fake_provider = AsyncMock()
    fake_provider.find_track_for_user.return_value = None  # no match

    with patch(
        "services.host_transfer_service.get_provider_client",
        return_value=fake_provider,
    ):
        state2 = await host_transfer_service.accept_transfer(
            room.roomId, transfer_id, invitee_id
        )

    entry = await queue_entry_repo.get_queue_entry(entry_id)
    assert entry is not None
    assert entry.status == QueueEntryStatus.REMOVED

    messages = state2.get("systemMessages")
    assert isinstance(messages, list) and len(messages) == 1
    assert "removed" in messages[0]["text"].lower()


@pytest.mark.asyncio
async def test_accept_transfer_ignores_history_entries(db_session, init_room):
    """Played/skipped history entries must not be remapped, removed, or counted."""
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _link_provider(invitee_id, room.supportedProviderId, db_session)

    played_id = await _add_track_and_queue_entry(
        room.roomId, host_id, db_session, title="Played"
    )
    skipped_id = await _add_track_and_queue_entry(
        room.roomId, host_id, db_session, title="Skipped"
    )
    queued_id = await _add_track_and_queue_entry(
        room.roomId, host_id, db_session, title="Queued"
    )
    await queue_entry_repo.update_queue_entry(
        played_id, {"status": QueueEntryStatus.PLAYED}, session=db_session
    )
    await queue_entry_repo.update_queue_entry(
        skipped_id, {"status": QueueEntryStatus.SKIPPED}, session=db_session
    )
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    # Provider matches nothing; only the active queued entry should be affected.
    fake_provider = AsyncMock()
    fake_provider.find_track_for_user.return_value = None

    with patch(
        "services.host_transfer_service.get_provider_client",
        return_value=fake_provider,
    ):
        state2 = await host_transfer_service.accept_transfer(
            room.roomId, transfer_id, invitee_id
        )

    # History entries are untouched.
    played = await queue_entry_repo.get_queue_entry(played_id)
    skipped = await queue_entry_repo.get_queue_entry(skipped_id)
    assert played is not None and played.status == QueueEntryStatus.PLAYED
    assert skipped is not None and skipped.status == QueueEntryStatus.SKIPPED

    # Only the active queued entry is removed.
    queued = await queue_entry_repo.get_queue_entry(queued_id)
    assert queued is not None and queued.status == QueueEntryStatus.REMOVED

    # The "find_track_for_user" provider call should only have run for the active entry.
    assert fake_provider.find_track_for_user.await_count == 1

    # Message reports exactly one removed song, not three.
    messages = state2.get("systemMessages")
    assert isinstance(messages, list) and len(messages) == 1
    assert messages[0]["text"].lower().startswith("1 song removed")


@pytest.mark.asyncio
async def test_accept_transfer_advances_when_playing_is_removed(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _link_provider(invitee_id, room.supportedProviderId, db_session)

    # Two entries: one currently playing (will be removed), one queued (will be matched).
    playing_id = await _add_track_and_queue_entry(
        room.roomId, host_id, db_session, title="Gone"
    )
    next_id = await _add_track_and_queue_entry(
        room.roomId, host_id, db_session, title="Survivor"
    )
    await queue_entry_repo.update_queue_entry(
        playing_id, {"status": QueueEntryStatus.PLAYING}, session=db_session
    )
    await playback_session_repo.create_playback_session(
        {
            "playbackSessionId": str(uuid.uuid4()),
            "roomId": room.roomId,
            "queueEntryId": playing_id,
            "state": PlaybackState.PLAYING,
            "elapsedTime": 0,
        },
        session=db_session,
    )
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    async def selective_match(*, user_id, title, artist):  # noqa: ARG001
        return None if title == "Gone" else _fake_match()

    fake_provider = AsyncMock()
    fake_provider.find_track_for_user.side_effect = selective_match

    with patch(
        "services.host_transfer_service.get_provider_client",
        return_value=fake_provider,
    ):
        await host_transfer_service.accept_transfer(
            room.roomId, transfer_id, invitee_id
        )

    removed = await queue_entry_repo.get_queue_entry(playing_id)
    survivor = await queue_entry_repo.get_queue_entry(next_id)
    # Unmatched playing entry is no longer active (either REMOVED by mapping or
    # PLAYED by _advance_to_next; both achieve "skip to next available").
    assert removed is not None
    assert removed.status in (QueueEntryStatus.REMOVED, QueueEntryStatus.PLAYED)
    # _advance_to_next promoted the survivor.
    assert survivor is not None and survivor.status == QueueEntryStatus.PLAYING


@pytest.mark.asyncio
async def test_accept_transfer_without_linked_provider_400(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    # NOTE: no provider linked for invitee
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.accept_transfer(
            room.roomId, transfer_id, invitee_id
        )
    assert exc.value.status_code == 400
    # transfer is still pending after a failed accept
    assert room_state_service.room_state_cache[room.roomId].get("transfer") is not None


@pytest.mark.asyncio
async def test_accept_transfer_wrong_user_403(db_session, init_room):
    host_id = str(uuid.uuid4())
    invitee_id = str(uuid.uuid4())
    third_id = str(uuid.uuid4())
    room = await init_room(user_id=host_id)
    await _add_member(invitee_id, room.roomId, db_session)
    await _add_member(third_id, room.roomId, db_session)
    await db_session.commit()

    state = await host_transfer_service.initiate_transfer(
        room.roomId, host_id, invitee_id
    )
    transfer_id = cast(dict, state["transfer"])["transferId"]

    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.accept_transfer(room.roomId, transfer_id, third_id)
    assert exc.value.status_code == 403
