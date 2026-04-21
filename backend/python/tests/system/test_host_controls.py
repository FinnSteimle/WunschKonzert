import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


@pytest.mark.system
def test_sc15_only_host_can_delete_room(browser: Browser, test_environment):
    """SC-15: Only host can delete the room"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Host sees delete button
    assert host.locator('[data-testid="delete-room-button"]').is_visible()

    # Guest doesn't see delete button
    assert not guest.locator('[data-testid="delete-room-button"]').is_visible()

    # Host deletes room
    host.click('[data-testid="delete-room-button"]')
    host.click('[data-testid="confirm-delete"]')

    # Both redirected
    host.wait_for_url("**/", timeout=5000)
    guest.wait_for_url("**/", timeout=5000)

    context.close()


@pytest.mark.system
def test_sc16_host_can_kick_user(browser: Browser, test_environment):
    """SC-16: Host can kick a user from the room"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Verify guest joined
    assert host.locator("text=Guest").is_visible(timeout=5000)

    # Host kicks guest
    host.locator('[data-testid="user-menu-Guest"]').click()
    host.click("text=Kick")

    # Guest is removed
    assert not host.locator("text=Guest").is_visible(timeout=5000)

    # Guest sees kicked message
    assert guest.locator("text=You have been kicked").is_visible(timeout=5000)

    context.close()


@pytest.mark.system
def test_sc17_host_can_remove_song_from_queue(browser: Browser, test_environment):
    """SC-17: Host can remove any song from queue"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Guest adds song
    add_song_helper(guest, "Test Song")

    # Host sees remove button
    assert (
        host.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="remove-song"]')
        .is_visible()
    )

    # Guest doesn't see remove button (not their song, not host)
    assert (
        not guest.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="remove-song"]')
        .is_visible()
    )

    # Host removes song
    host.locator('[data-testid="queue-item"]', has_text="Test Song").locator(
        '[data-testid="remove-song"]'
    ).click()

    # Song removed for both
    assert not host.locator(
        '[data-testid="queue-item"]', has_text="Test Song"
    ).is_visible(timeout=5000)
    assert not guest.locator(
        '[data-testid="queue-item"]', has_text="Test Song"
    ).is_visible(timeout=5000)

    context.close()


@pytest.mark.system
def test_sc18_user_can_remove_own_song(browser: Browser, test_environment):
    """SC-18: User can remove their own song from queue"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Guest adds song
    add_song_helper(guest, "My Song")

    # Guest sees remove button on their own song
    assert (
        guest.locator('[data-testid="queue-item"]', has_text="My Song")
        .locator('[data-testid="remove-song"]')
        .is_visible()
    )

    # Guest removes their song
    guest.locator('[data-testid="queue-item"]', has_text="My Song").locator(
        '[data-testid="remove-song"]'
    ).click()

    # Song removed for both
    assert not guest.locator(
        '[data-testid="queue-item"]', has_text="My Song"
    ).is_visible(timeout=5000)
    assert not host.locator(
        '[data-testid="queue-item"]', has_text="My Song"
    ).is_visible(timeout=5000)

    context.close()
