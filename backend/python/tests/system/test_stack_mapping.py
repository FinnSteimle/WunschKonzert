import pytest
from playwright.sync_api import Browser

from tests.system.conftest import create_room_helper, join_room_helper


@pytest.mark.system
def test_system_mapping_create_and_join(browser: Browser, test_environment):
    """Frontend and backend are correctly mapped for create/join room flow."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    members = 'ul[aria-label="Room members"] li'
    assert host.locator(members, has_text="Guest").is_visible(timeout=10000)
    assert guest.locator(members, has_text="Host").is_visible(timeout=10000)

    context.close()


@pytest.mark.system
def test_system_mapping_invalid_room_slug_shows_error(
    browser: Browser, test_environment
):
    """Frontend route mapping works and surfaces invalid room slug errors."""
    page = browser.new_page()
    page.goto(
        f"{test_environment['frontend_url']}/room/INVALID",
        wait_until="domcontentloaded",
    )
    assert page.locator("text=This link is not a valid room or join code.").is_visible(
        timeout=10000
    )
    page.close()


@pytest.mark.system
def test_system_mapping_nonexistent_join_code_shows_backend_error(
    browser: Browser, test_environment
):
    """Frontend reaches backend and surfaces backend room-not-found response."""
    page = browser.new_page()
    page.goto(
        f"{test_environment['frontend_url']}/room/ABCDEF", wait_until="domcontentloaded"
    )
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.fill('input[name="displayName"]', "User")
    page.click('button:has-text("Join room")')
    room_not_found = page.locator("text=Room not found")
    room_unavailable = page.locator("text=Room unavailable")
    page.wait_for_function(
        """
        () => document.body.innerText.includes('Room not found')
           || document.body.innerText.includes('Room unavailable')
        """
    )
    assert room_not_found.is_visible() or room_unavailable.is_visible()
    page.close()
