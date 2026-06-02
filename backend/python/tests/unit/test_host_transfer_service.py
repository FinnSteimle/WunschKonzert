from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain import MembershipStatus, QueueEntryStatus
from services import host_transfer_service

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_room_state_cache():
    with patch("services.room_state_service.room_state_cache", {}) as cache:
        yield cache


@pytest.mark.asyncio
async def test_initiate_transfer_success():
    room_id = "r1"
    from_user = "u1"
    to_user = "u2"

    mock_room = MagicMock(hostedBy=from_user)
    mock_membership = MagicMock(membershipStatus=MembershipStatus.ACTIVE)

    with (
        patch("repositories.room_repo.get_room", return_value=mock_room),
        patch(
            "repositories.membership_repo.get_room_membership",
            return_value=mock_membership,
        ),
        patch(
            "services.room_state_service.build_last_activity", new_callable=AsyncMock
        ),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch("services.room_state_service.room_state_cache", {room_id: {}}),
    ):
        result = await host_transfer_service.initiate_transfer(
            room_id, from_user, to_user
        )

        assert "transfer" in result
        assert result["transfer"]["fromUserId"] == from_user
        assert result["transfer"]["toUserId"] == to_user


@pytest.mark.asyncio
async def test_initiate_transfer_same_user_raises():
    with pytest.raises(HTTPException) as exc:
        await host_transfer_service.initiate_transfer("r1", "u1", "u1")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_accept_transfer_success_with_remap():
    room_id = "r1"
    transfer_id = "t1"
    user_id = "u2"

    mock_room = MagicMock(supportedProviderId="spotify", hostedBy="u1")
    mock_transfer = {"transferId": transfer_id, "toUserId": user_id}

    # Mocking queue entries
    mock_entry = MagicMock(
        queueEntryId="qe1", trackId="track1", status=QueueEntryStatus.QUEUED
    )
    mock_track = MagicMock(title="Title", artist="Artist")
    mock_match = MagicMock(
        track_id="track2",
        provider_track_id="p1",
        title="Title",
        artist="Artist",
        album="Album",
        duration=120,
    )

    with (
        patch(
            "services.host_transfer_service._get_transfer", return_value=mock_transfer
        ),
        patch("repositories.room_repo.get_room", return_value=mock_room),
        patch(
            "repositories.music_provider_repo.get_provider_account_by_user",
            return_value=MagicMock(),
        ),
        patch("services.host_transfer_service.is_account_linked", return_value=True),
        patch(
            "repositories.queue_entry_repo.get_queue_entries", return_value=[mock_entry]
        ),
        patch("repositories.track_repo.get_track", side_effect=[mock_track, None]),
        patch(
            "services.providers.registry.get_provider_client", return_value=MagicMock()
        ),
        patch("services.host_transfer_service._find_match", return_value=mock_match),
        patch("repositories.track_repo.create_track", new_callable=AsyncMock),
        patch(
            "repositories.queue_entry_repo.update_queue_entry", new_callable=AsyncMock
        ) as mock_update_qe,
        patch("repositories.room_repo.update_host", new_callable=AsyncMock),
        patch(
            "services.playback_service.set_playback_state",
            new_callable=AsyncMock,
        ) as mock_set_state,
        patch(
            "services.room_state_service.build_last_activity", new_callable=AsyncMock
        ),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch(
            "services.room_state_service.room_state_cache",
            {room_id: {"playback": {"state": "playing"}}},
        ),
    ):
        await host_transfer_service.accept_transfer(room_id, transfer_id, user_id)

        # Verify entry remapped to track2
        mock_update_qe.assert_called_with("qe1", {"trackId": "track2"})
        mock_set_state.assert_called_once_with(room_id, "u1", "pause")


@pytest.mark.asyncio
async def test_accept_transfer_song_removed():
    room_id = "r1"
    transfer_id = "t1"
    user_id = "u2"

    mock_room = MagicMock(supportedProviderId="spotify")
    mock_transfer = {"transferId": transfer_id, "toUserId": user_id}

    # Mocking queue entry that has no match
    mock_entry = MagicMock(
        queueEntryId="qe1", trackId="track1", status=QueueEntryStatus.PLAYING
    )
    mock_track = MagicMock(title="No Match", artist="Artist")

    with (
        patch(
            "services.host_transfer_service._get_transfer", return_value=mock_transfer
        ),
        patch("repositories.room_repo.get_room", return_value=mock_room),
        patch(
            "repositories.music_provider_repo.get_provider_account_by_user",
            return_value=MagicMock(),
        ),
        patch("services.host_transfer_service.is_account_linked", return_value=True),
        patch(
            "repositories.queue_entry_repo.get_queue_entries", return_value=[mock_entry]
        ),
        patch("repositories.track_repo.get_track", return_value=mock_track),
        patch(
            "services.providers.registry.get_provider_client", return_value=MagicMock()
        ),
        patch("services.host_transfer_service._find_match", return_value=None),
        patch(
            "repositories.queue_entry_repo.update_queue_entry", new_callable=AsyncMock
        ) as mock_update_qe,
        patch(
            "services.playback_service.advance_to_next", new_callable=AsyncMock
        ) as mock_advance,
        patch(
            "services.playback_service.set_playback_state",
            new_callable=AsyncMock,
        ) as mock_set_state,
        patch("repositories.room_repo.update_host", new_callable=AsyncMock),
        patch(
            "services.room_state_service.build_last_activity", new_callable=AsyncMock
        ),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch("services.room_state_service.room_state_cache", {room_id: {}}),
    ):
        await host_transfer_service.accept_transfer(room_id, transfer_id, user_id)

        # Verify entry REMOVED
        mock_update_qe.assert_called_with("qe1", {"status": QueueEntryStatus.REMOVED})
        # Verify playback advanced because playing track was removed
        mock_advance.assert_called_once_with(room_id)
        mock_set_state.assert_not_called()


@pytest.mark.asyncio
async def test_reject_transfer_success():
    room_id = "r1"
    transfer_id = "t1"
    user_id = "u2"

    mock_transfer = {"transferId": transfer_id, "toUserId": user_id}

    with (
        patch(
            "services.host_transfer_service._get_transfer", return_value=mock_transfer
        ),
        patch("services.host_transfer_service._set_transfer") as mock_set,
        patch(
            "services.room_state_service.build_last_activity", new_callable=AsyncMock
        ),
        patch("services.room_state_service.refresh_room_state", new_callable=AsyncMock),
        patch("services.room_state_service.room_state_cache", {room_id: {}}),
    ):
        await host_transfer_service.reject_transfer(room_id, transfer_id, user_id)
        mock_set.assert_called_with(room_id, None)


@pytest.mark.asyncio
async def test_reject_transfer_wrong_user_raises():
    room_id = "r1"
    mock_transfer = {"transferId": "t1", "toUserId": "u2"}

    with patch(
        "services.host_transfer_service._get_transfer", return_value=mock_transfer
    ):
        with pytest.raises(HTTPException) as exc:
            await host_transfer_service.reject_transfer(room_id, "t1", "wrong_user")
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_accept_transfer_not_linked_raises():
    room_id = "r1"
    user_id = "u2"
    mock_room = MagicMock(supportedProviderId="spotify")
    mock_transfer = {"transferId": "t1", "toUserId": user_id}

    with (
        patch(
            "services.host_transfer_service._get_transfer", return_value=mock_transfer
        ),
        patch("repositories.room_repo.get_room", return_value=mock_room),
        patch(
            "repositories.music_provider_repo.get_provider_account_by_user",
            return_value=None,
        ),
        patch("services.host_transfer_service.is_account_linked", return_value=False),
    ):
        with pytest.raises(HTTPException) as exc:
            await host_transfer_service.accept_transfer(room_id, "t1", user_id)
        assert exc.value.status_code == 400
        assert "Link your music provider" in exc.value.detail
