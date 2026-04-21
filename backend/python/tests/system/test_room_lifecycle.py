import pytest
from playwright.sync_api import Browser

from tests.system.conftest import create_room_helper, join_room_helper


@pytest.mark.system
def test_sc1_host_creates_room_guest_joins(browser: Browser, test_environment):
    """SC-1: Host creates room, guest joins, both see room state via WebSocket"""
    context = browser.new_context()

    # Host creates room
    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Alice")

    # Guest joins
    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Bob")

    # Verify WebSocket sync - both see each other
    assert host.locator("text=Bob").is_visible(timeout=5000)
    assert guest.locator("text=Alice").is_visible(timeout=5000)

    # Verify member count
    host_count = host.locator('[data-testid="member-count"]').text_content()
    guest_count = guest.locator('[data-testid="member-count"]').text_content()
    assert host_count == "2"
    assert guest_count == "2"

    context.close()


@pytest.mark.system
def test_sc2_guest_leaves_room_updates_sync(browser: Browser, test_environment):
    """SC-2: Guest leaves room, host sees update in real-time"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Verify guest joined
    assert host.locator("text=Guest").is_visible(timeout=5000)

    # Guest leaves
    guest.click('[data-testid="leave-button"]')

    # Host sees guest left
    assert not host.locator("text=Guest").is_visible(timeout=5000)
    assert host.locator('[data-testid="member-count"]').text_content() == "1"

    context.close()


@pytest.mark.system
def test_sc3_invalid_join_code_shows_error(browser: Browser, test_environment):
    """SC-3: Joining with invalid code shows error"""
    context = browser.new_context()
    page = context.new_page()

    page.goto(
        f"{test_environment['frontend_url']}/join/INVALID",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.fill('input[name="displayName"]', "User")
    page.click('button:has-text("Join")')

    # Verify error message
    assert page.locator("text=Room not found").is_visible(timeout=5000)

    context.close()


@pytest.mark.system
def test_sc4_room_state_persists_after_refresh(browser: Browser, test_environment):
    """SC-4: Room state persists in database after page refresh"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Refresh host page
    host.reload()

    # Verify state restored
    assert host.locator("text=Guest").is_visible(timeout=5000)
    assert host.locator('[data-testid="join-code"]').text_content().strip() == join_code

    context.close()
