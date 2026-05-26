import pytest
from playwright.sync_api import Browser, Page

from tests.system.conftest import (
    add_track_to_room,
    create_room_helper,
    get_room_state_snapshot,
    join_room_helper,
    user_id_for_display_name,
)


def queue_item(page: Page, song_name: str):
    return (
        page.get_by_role("list", name="Playback queue")
        .get_by_role("listitem")
        .filter(has_text=song_name)
    )


@pytest.mark.system
def test_sc15_only_host_can_delete_room(browser: Browser, test_environment):
    """SC-15: Only host can delete the room."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    assert host.get_by_role("button", name="Delete room").is_visible()
    assert guest.get_by_role("button", name="Delete room").count() == 0

    host.get_by_role("button", name="Delete room").click()
    host.get_by_role("button", name="Delete forever").click()

    host.wait_for_url("**/", timeout=5000)
    guest.wait_for_url("**/", timeout=5000)

    context.close()


@pytest.mark.system
def test_sc17_host_can_remove_song_from_queue(browser: Browser, test_environment):
    """SC-17: Host can remove any song from queue."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Alpha")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Beta")

    queue_item(host, "Beta").get_by_role("button", name="Remove track").click()

    host.wait_for_function(
        """
        needle => {
            const list = document.querySelector('[aria-label="Playback queue"]');
            if (!list) return true;
            return !list.innerText.includes(needle);
        }
        """,
        arg="Beta",
    )
    assert queue_item(host, "Beta").count() == 0
    assert queue_item(guest, "Beta").count() == 0

    context.close()


@pytest.mark.system
def test_sc18_user_can_remove_own_song(browser: Browser, test_environment):
    """SC-18: User can remove a song they added to the queue."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    guest_id = user_id_for_display_name(room_state, "Guest")

    add_track_to_room(test_environment["backend_url"], join_code, guest_id, "Host Song")
    add_track_to_room(
        test_environment["backend_url"], join_code, guest_id, "Guest Song"
    )

    queue_item(guest, "Guest Song").get_by_role("button", name="Remove track").click()

    host.wait_for_function(
        """
        needle => {
            const list = document.querySelector('[aria-label="Playback queue"]');
            if (!list) return true;
            return !list.innerText.includes(needle);
        }
        """,
        arg="Guest Song",
    )
    assert queue_item(host, "Guest Song").count() == 0
    assert queue_item(guest, "Guest Song").count() == 0

    context.close()
