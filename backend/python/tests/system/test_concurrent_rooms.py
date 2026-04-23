import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


def queue_item(page, song_name: str):
    return (
        page.get_by_role("list", name="Playback queue")
        .get_by_role("listitem")
        .filter(has_text=song_name)
    )


@pytest.mark.skip(
    reason="Concurrent-room queue isolation is blocked by the unstable song search/add flow."
)
@pytest.mark.system
def test_sc19_concurrent_rooms_remain_isolated(browser: Browser, test_environment):
    """SC-19: Multiple concurrent rooms don't interfere with each other"""
    # TODO: Re-enable once queue setup via the search UI is deterministic in
    # system tests; this isolation check currently times out before queue state exists.
    pass


@pytest.mark.system
def test_sc20_users_in_different_rooms_dont_see_each_other(
    browser: Browser, test_environment
):
    """SC-20: Users in different rooms don't see each other"""
    context = browser.new_context()

    # Room 1
    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Alice")

    room1_guest = context.new_page()
    join_room_helper(room1_guest, test_environment["frontend_url"], code1, "Bob")

    # Room 2
    room2_host = context.new_page()
    code2 = create_room_helper(room2_host, test_environment["frontend_url"], "Charlie")

    room2_guest = context.new_page()
    join_room_helper(room2_guest, test_environment["frontend_url"], code2, "Diana")

    # Room 1 sees Alice and Bob only
    assert room1_host.locator("text=Alice").is_visible()
    assert room1_host.locator("text=Bob").is_visible()
    assert not room1_host.locator("text=Charlie").is_visible()
    assert not room1_host.locator("text=Diana").is_visible()

    # Room 2 sees Charlie and Diana only
    assert room2_host.locator("text=Charlie").is_visible()
    assert room2_host.locator("text=Diana").is_visible()
    assert not room2_host.locator("text=Alice").is_visible()
    assert not room2_host.locator("text=Bob").is_visible()

    context.close()


@pytest.mark.skip(
    reason="Deterministic playback-state assertions are not exposed in the current system-test setup."
)
@pytest.mark.system
def test_sc21_playback_in_one_room_doesnt_affect_other(
    browser: Browser, test_environment
):
    """SC-21: Playback in one room doesn't affect other rooms"""
    pass


@pytest.mark.skip(
    reason="Concurrent-room vote isolation is blocked by the unstable song search/add flow."
)
@pytest.mark.system
def test_sc22_votes_in_one_room_dont_affect_other(browser: Browser, test_environment):
    """SC-22: Votes in one room don't affect queue in other rooms"""
    # TODO: Re-enable after SC-19/SC-5 are stable; this depends on deterministic
    # queue population before cross-room vote isolation can be asserted.
    pass
