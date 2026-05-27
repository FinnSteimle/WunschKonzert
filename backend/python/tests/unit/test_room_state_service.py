from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ResourceNotFoundError
from models.domain import (
    FeedbackType,
    MembershipStatus,
    PlaybackSession,
    PlaybackState,
    QueueEntry,
    QueueEntryStatus,
    Room,
    RoomMembership,
    SongFeedback,
    Track,
    User,
)
from services.room_state_service import (
    _build_playback_state,
    _build_queue_list,
    _build_room_state,
    _build_user_list,
    _preserve_ephemeral_fields,
    build_last_activity,
    refresh_room_state,
    room_state_cache,
)

pytestmark = pytest.mark.unit

...


@pytest.mark.asyncio
async def test_refresh_room_state_success():
    room_id = "r1"
    mock_state = {"room": {"roomId": room_id}}
    with patch(
        "services.room_state_service._build_room_state", new_callable=AsyncMock
    ) as mock_build:
        mock_build.return_value = mock_state

        result = await refresh_room_state(room_id, event_type="test_event")

        assert result["room"]["roomId"] == room_id
        assert "lastEvent" in result
        assert result["lastEvent"]["type"] == "test_event"
        assert room_state_cache[room_id] == result


@pytest.mark.asyncio
async def test_build_last_activity_success():
    mock_session = AsyncMock()
    mock_user = MagicMock(displayName="Display Name")

    with (
        patch(
            "repositories.user_repo.get_user", new_callable=AsyncMock
        ) as mock_get_user,
        patch(
            "services.room_state_service._now_iso", return_value="2024-01-01T00:00:00Z"
        ),
    ):
        mock_get_user.return_value = mock_user

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "AccountUser"
        mock_session.execute.return_value = mock_result

        activity = await build_last_activity("test_act", "u1", session=mock_session)

        assert activity["type"] == "test_act"
        assert activity["username"] == "AccountUser"
        assert activity["at"] == "2024-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_build_room_state_not_found():
    mock_session = AsyncMock()
    with patch(
        "repositories.room_repo.get_room_with_full_state",
        side_effect=ResourceNotFoundError("No room"),
    ):
        result = await _build_room_state("r1", session=mock_session)
        assert result is None


def test_build_user_list_removes_duplicates_and_inactive():
    # Create an in-memory host
    host = User(userId="host1", displayName="Host", createdAt=datetime.now(UTC))

    # Create a room object manually (no DB)
    room = Room(
        roomId="room1",
        name="Test Room",
        createdAt=datetime.now(UTC),
        host=host,
        hostedBy="host1",
    )

    # Add some memberships
    guest = User(userId="guest1", displayName="Guest", createdAt=datetime.now(UTC))
    room.memberships = [
        # Active guest
        RoomMembership(
            user=guest,
            userId="guest1",
            membershipStatus=MembershipStatus.ACTIVE,
            joinedAt=datetime.now(UTC),
        ),
        # Inactive guest (should be filtered out)
        RoomMembership(
            user=User(userId="left", displayName="Left", createdAt=datetime.now(UTC)),
            userId="left",
            membershipStatus=MembershipStatus.INACTIVE,
            joinedAt=datetime.now(UTC),
        ),
        # Duplicate of host (should be filtered out)
        RoomMembership(
            user=host,
            userId="host1",
            membershipStatus=MembershipStatus.ACTIVE,
            joinedAt=datetime.now(UTC),
        ),
    ]

    result = _build_user_list(room)

    # Should only have 2 users: host and the active guest
    assert len(result) == 2
    user_ids = [u["user"]["userId"] for u in result]
    assert "host1" in user_ids
    assert "guest1" in user_ids
    assert "left" not in user_ids


def test_build_queue_list_complex_sorting():
    """Verify: 1. Playing is first. 2. Higher voteScore next. 3. Lower position tie-break."""
    host = User(userId="host", displayName="Host")
    room = Room(host=host)

    # Song A: Position 1, Score 0 (QUEUED)
    entry_a = QueueEntry(
        queueEntryId="a",
        track=Track(title="A", artist="A"),
        added_by=host,
        position=1,
        status=QueueEntryStatus.QUEUED,
        song_feedback=[],
        orderRank=1.0,
        queuedAt=datetime.now(UTC),
    )
    # Song B: Position 2, Score 10 (QUEUED) - Should jump to 2nd place
    entry_b = QueueEntry(
        queueEntryId="b",
        track=Track(title="B", artist="B"),
        added_by=host,
        position=2,
        status=QueueEntryStatus.QUEUED,
        song_feedback=[
            SongFeedback(type=FeedbackType.LIKE, votedAt=datetime.now(UTC))
            for _ in range(10)
        ],
        orderRank=2.0,
        queuedAt=datetime.now(UTC),
    )
    # Song C: Position 3, Score 0 (PLAYING) - Should jump to 1st place
    entry_c = QueueEntry(
        queueEntryId="c",
        track=Track(title="C", artist="C"),
        added_by=host,
        position=3,
        status=QueueEntryStatus.PLAYING,
        song_feedback=[],
        orderRank=3.0,
        queuedAt=datetime.now(UTC),
    )

    room.queue_entries = [entry_a, entry_b, entry_c]

    result = _build_queue_list(room)

    titles = [item["track"]["title"] for item in result]
    # Expected order: C (playing), B (score 10), A (score 0)
    assert titles == ["C", "B", "A"]


def test_preserve_ephemeral_fields():
    """Verify that in-memory fields are kept during a refresh."""
    room_id = "test_room"
    # 1. Setup a "previous" state in the cache
    room_state_cache[room_id] = {
        "lastActivity": {"type": "user_joined", "userId": "u1"},
        "transfer": {"transferId": "t123", "toUserId": "u2"},
        "systemMessages": [{"id": "m1", "text": "Hello"}],
    }

    # 2. A "new" fresh state from the DB (which doesn't know about memory-only fields)
    new_state = {"room": {"roomId": room_id}, "users": []}

    _preserve_ephemeral_fields(room_id, new_state)

    # 3. Verify fields were carried over
    assert new_state["lastActivity"]["type"] == "user_joined"
    assert new_state["transfer"]["transferId"] == "t123"
    assert new_state["systemMessages"][0]["text"] == "Hello"


def test_build_playback_state_stopped():
    """Verify state when no playback session exists."""
    room = Room(playback_sessions=[])

    state = _build_playback_state(room)

    assert state["state"] == "stopped"
    assert state["currentQueueEntryId"] is None
    assert state["positionMs"] == 0


def test_build_playback_state_playing():
    """Verify state when a session is active."""
    session = PlaybackSession(
        playbackSessionId="ps1",
        queueEntryId="qe1",
        state=PlaybackState.PLAYING,
        elapsedTime=45,  # 45 seconds
        startedAt=datetime.now(UTC),
    )
    room = Room(playback_sessions=[session])

    state = _build_playback_state(room)

    assert state["state"] == "playing"
    assert state["currentQueueEntryId"] == "qe1"
    assert state["positionMs"] == 45000
