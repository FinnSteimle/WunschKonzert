import pytest
from playwright.sync_api import Browser

from tests.system.conftest import create_room_helper, join_room_helper


@pytest.mark.system
def test_sc15_only_host_can_delete_room(browser: Browser, test_environment):
    """SC-15: Only host can delete the room"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Host sees delete button in the room footer.
    assert host.get_by_role("button", name="Delete room").is_visible()

    # Guests only get leave/home actions, not host-only deletion.
    assert guest.get_by_role("button", name="Delete room").count() == 0

    # Host deletes room
    host.get_by_role("button", name="Delete room").click()
    host.get_by_role("button", name="Delete forever").click()

    # Both redirected
    host.wait_for_url("**/", timeout=5000)
    guest.wait_for_url("**/", timeout=5000)

    context.close()


@pytest.mark.skip(
    reason="Current room page does not expose a kick-user control in UserList.svelte."
)
@pytest.mark.system
def test_sc16_host_can_kick_user(browser: Browser, test_environment):
    """SC-16: Host can kick a user from the room"""
    pass


@pytest.mark.skip(
    reason="Current queue UI has voting only; no host-only remove-song control is rendered."
)
@pytest.mark.system
def test_sc17_host_can_remove_song_from_queue(browser: Browser, test_environment):
    """SC-17: Host can remove any song from queue"""
    pass


@pytest.mark.skip(
    reason="Current queue UI does not expose a remove-song action for the submitting user."
)
@pytest.mark.system
def test_sc18_user_can_remove_own_song(browser: Browser, test_environment):
    """SC-18: User can remove their own song from queue"""
    pass
