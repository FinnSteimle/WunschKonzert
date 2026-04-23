import pytest
from playwright.sync_api import Browser

from tests.system.conftest import create_room_helper, join_room_helper


def member_item(page, name: str):
    return page.get_by_role("list", name="Room members").get_by_role("listitem").filter(
        has_text=name
    )


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

    # Verify both see exactly two active members in the room list.
    assert host.get_by_role("list", name="Room members").get_by_role("listitem").count() == 2
    assert guest.get_by_role("list", name="Room members").get_by_role("listitem").count() == 2

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
    guest.get_by_role("button", name="Leave room").click()

    # Host sees guest left
    member_item(host, "Guest").first.wait_for(state="hidden", timeout=10000)
    assert host.get_by_role("list", name="Room members").get_by_role("listitem").count() == 1

    context.close()


@pytest.mark.system
def test_sc3_invalid_join_code_shows_error(browser: Browser, test_environment):
    """SC-3: Joining with invalid code shows error"""
    context = browser.new_context()
    page = context.new_page()

    page.goto(
        f"{test_environment['frontend_url']}/room/ABCDEF",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.fill('input[name="displayName"]', "User")
    page.click('button:has-text("Join room")')

    # Verify error message
    room_not_found = page.locator("text=Room not found")
    room_unavailable = page.locator("text=Room unavailable")
    page.wait_for_function(
        """
        () => document.body.innerText.includes('Room not found')
           || document.body.innerText.includes('Room unavailable')
        """
    )
    assert room_not_found.is_visible() or room_unavailable.is_visible()

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
    host.wait_for_selector("text=Who is here", state="visible")

    # Verify state restored
    assert host.locator("text=Guest").is_visible(timeout=5000)
    assert host.locator(f"text=Code {join_code}").is_visible()

    context.close()
