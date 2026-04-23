import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


@pytest.mark.skip(
    reason="Deterministic playback start/pause is not exposed in the current system-test setup."
)
@pytest.mark.system
def test_sc10_host_starts_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-10: Host starts playback, all participants see playing state"""
    pass


@pytest.mark.skip(
    reason="Deterministic playback start/pause is not exposed in the current system-test setup."
)
@pytest.mark.system
def test_sc11_host_pauses_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-11: Host pauses playback, all participants see paused state"""
    pass


@pytest.mark.skip(
    reason="Host-only playback control visibility is blocked by the unstable song search/add flow."
)
@pytest.mark.system
def test_sc12_guest_cannot_control_playback(browser: Browser, test_environment):
    """SC-12: Guest does not see playback controls (host-only)"""
    # TODO: Re-enable once queue setup via the search UI is deterministic; this
    # scenario cannot reach the host-only playback controls without a queued song.
    pass


@pytest.mark.skip(
    reason="Current room page exposes no deterministic skip-to-next control for system tests."
)
@pytest.mark.system
def test_sc13_playback_advances_to_next_song(browser: Browser, test_environment):
    """SC-13: When song ends, playback advances to next in queue"""
    pass


@pytest.mark.skip(
    reason="Playback progress text is not stable enough for deterministic cross-client system assertions."
)
@pytest.mark.system
def test_sc14_playback_position_syncs(browser: Browser, test_environment):
    """SC-14: Playback position syncs across clients"""
    pass
