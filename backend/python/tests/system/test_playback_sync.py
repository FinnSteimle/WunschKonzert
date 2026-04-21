import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


@pytest.mark.system
def test_sc10_host_starts_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-10: Host starts playback, all participants see playing state"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song
    add_song_helper(host, "Test Song")

    # Host starts playback
    host.click('[data-testid="play-button"]')

    # Both see playing state
    assert (
        host.locator('[data-testid="playback-state"]').text_content(timeout=5000)
        == "playing"
    )
    assert (
        guest.locator('[data-testid="playback-state"]').text_content(timeout=5000)
        == "playing"
    )

    context.close()


@pytest.mark.system
def test_sc11_host_pauses_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-11: Host pauses playback, all participants see paused state"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song and start playback
    add_song_helper(host, "Test Song")
    host.click('[data-testid="play-button"]')

    # Wait for playing state
    host.wait_for_selector('[data-testid="playback-state"]:has-text("playing")')

    # Host pauses
    host.click('[data-testid="pause-button"]')

    # Both see paused state
    assert (
        host.locator('[data-testid="playback-state"]').text_content(timeout=5000)
        == "paused"
    )
    assert (
        guest.locator('[data-testid="playback-state"]').text_content(timeout=5000)
        == "paused"
    )

    context.close()


@pytest.mark.system
def test_sc12_guest_cannot_control_playback(browser: Browser, test_environment):
    """SC-12: Guest does not see playback controls (host-only)"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song
    add_song_helper(host, "Test Song")

    # Host sees controls
    assert host.locator('[data-testid="play-button"]').is_visible()

    # Guest doesn't see controls
    assert not guest.locator('[data-testid="play-button"]').is_visible()

    context.close()


@pytest.mark.system
def test_sc13_playback_advances_to_next_song(browser: Browser, test_environment):
    """SC-13: When song ends, playback advances to next in queue"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add two songs
    add_song_helper(host, "Song 1")
    add_song_helper(host, "Song 2")

    # Start playback
    host.click('[data-testid="play-button"]')

    # Simulate song end (skip to next)
    host.click('[data-testid="skip-button"]')

    # Verify Song 2 is now playing
    assert (
        host.locator('[data-testid="now-playing"]').text_content(timeout=5000)
        == "Song 2"
    )
    assert (
        guest.locator('[data-testid="now-playing"]').text_content(timeout=5000)
        == "Song 2"
    )

    context.close()


@pytest.mark.system
def test_sc14_playback_position_syncs(browser: Browser, test_environment):
    """SC-14: Playback position syncs across clients"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song and start playback
    add_song_helper(host, "Test Song")
    host.click('[data-testid="play-button"]')

    # Wait a bit for playback to progress
    host.wait_for_timeout(2000)

    # Get positions
    host_position = host.locator('[data-testid="playback-position"]').text_content()
    guest_position = guest.locator('[data-testid="playback-position"]').text_content()

    # Positions should be close (within 1 second tolerance)
    assert abs(int(host_position) - int(guest_position)) <= 1

    context.close()
