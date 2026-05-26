import pytest
from playwright.sync_api import Browser, Page

from tests.system.conftest import (
    add_track_to_room,
    create_room_helper,
    get_room_state_snapshot,
    join_room_helper,
    parse_elapsed_seconds,
    send_room_event,
    user_id_for_display_name,
)


def playback_progress(page: Page):
    return page.get_by_label("Playback progress")


def wait_for_playback_state(page: Page, state: str) -> None:
    page.wait_for_function(
        """
        ([selector, expected]) => {
            const el = document.querySelector(selector);
            return !!el && el.innerText.includes(expected);
        }
        """,
        arg=["[aria-label='Playback progress']", state],
    )


@pytest.mark.system
def test_sc10_host_starts_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-10: Host starts playback and all participants see playing state."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Intro Track"
    )

    assert host.get_by_role("button", name="Resume").is_visible()
    assert guest.get_by_role("button", name="Resume").count() == 0

    playback_state = send_room_event(
        test_environment["backend_url"],
        join_code,
        {
            "type": "playback",
            "user_id": host_id,
            "action": "resume",
        },
        expected_last_event="playback_updated",
    )
    assert playback_state["playback"]["state"] == "playing"

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Pause",
    )
    assert guest.get_by_role("button", name="Pause").count() == 0

    updated_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    assert updated_state["playback"]["state"] == "playing"

    context.close()


@pytest.mark.system
def test_sc11_host_pauses_playback_syncs_to_all(browser: Browser, test_environment):
    """SC-11: Host pauses playback and all participants see paused state."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Intro Track"
    )

    send_room_event(
        test_environment["backend_url"],
        join_code,
        {
            "type": "playback",
            "user_id": host_id,
            "action": "resume",
        },
        expected_last_event="playback_updated",
    )
    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Pause",
    )

    paused_state = send_room_event(
        test_environment["backend_url"],
        join_code,
        {
            "type": "playback",
            "user_id": host_id,
            "action": "pause",
        },
        expected_last_event="playback_updated",
    )
    assert paused_state["playback"]["state"] == "paused"

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Resume",
    )
    updated_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    assert updated_state["playback"]["state"] == "paused"

    context.close()


@pytest.mark.system
def test_sc12_guest_cannot_control_playback(browser: Browser, test_environment):
    """SC-12: Guest does not see host-only playback controls."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Intro Track"
    )

    assert host.get_by_role("button", name="Resume").is_visible()
    assert guest.get_by_role("button", name="Resume").count() == 0
    assert guest.get_by_role("button", name="Pause").count() == 0

    context.close()


@pytest.mark.system
def test_sc13_playback_advances_to_next_song(browser: Browser, test_environment):
    """SC-13: Advancing playback updates the now-playing track for everyone."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "First Track"
    )
    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Second Track"
    )
    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Third Track"
    )

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Second Track",
    )
    guest.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Second Track",
    )

    send_room_event(
        test_environment["backend_url"],
        join_code,
        {
            "type": "playback",
            "user_id": host_id,
            "action": "advance",
        },
        expected_last_event="playback_updated",
    )

    host.wait_for_function(
        """
        needle => {
            const list = document.querySelector('[aria-label="Playback queue"]');
            if (!list) return false;
            return !list.innerText.includes(needle);
        }
        """,
        arg="Second Track",
    )
    assert host.get_by_text("Second Track").is_visible()
    assert guest.get_by_text("Second Track").is_visible()

    context.close()


@pytest.mark.system
def test_sc14_playback_position_syncs(browser: Browser, test_environment):
    """SC-14: Playback position stays in sync across clients."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Intro Track"
    )
    send_room_event(
        test_environment["backend_url"],
        join_code,
        {
            "type": "playback",
            "user_id": host_id,
            "action": "resume",
        },
        expected_last_event="playback_updated",
    )
    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Pause",
    )
    assert guest.get_by_role("button", name="Pause").count() == 0

    updated_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    assert updated_state["playback"]["state"] == "playing"

    host.wait_for_timeout(2200)

    host_elapsed = parse_elapsed_seconds(playback_progress(host).inner_text())
    guest_elapsed = parse_elapsed_seconds(playback_progress(guest).inner_text())

    assert abs(host_elapsed - guest_elapsed) <= 1

    context.close()
