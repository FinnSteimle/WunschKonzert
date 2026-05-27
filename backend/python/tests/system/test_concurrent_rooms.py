import pytest
from playwright.sync_api import Browser, Page

from tests.system.conftest import (
    add_track_to_room,
    create_room_helper,
    get_room_state_snapshot,
    join_room_helper,
    send_room_event,
    user_id_for_display_name,
)


def queue_item(page: Page, song_name: str):
    return (
        page.get_by_role("list", name="Playback queue")
        .get_by_role("listitem")
        .filter(has_text=song_name)
    )


@pytest.mark.system
def test_sc18_concurrent_rooms_remain_isolated(browser: Browser, test_environment):
    """SC-18: Queue updates in one room do not appear in another room."""
    context = browser.new_context()

    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Alice")

    room1_guest = context.new_page()
    join_room_helper(room1_guest, test_environment["frontend_url"], code1, "Bob")

    room2_host = context.new_page()
    code2 = create_room_helper(room2_host, test_environment["frontend_url"], "Charlie")

    room2_guest = context.new_page()
    join_room_helper(room2_guest, test_environment["frontend_url"], code2, "Diana")

    room1_state = get_room_state_snapshot(test_environment["backend_url"], code1)
    room1_host_id = user_id_for_display_name(room1_state, "Alice")

    room2_state = get_room_state_snapshot(test_environment["backend_url"], code2)
    room2_host_id = user_id_for_display_name(room2_state, "Charlie")

    add_track_to_room(
        test_environment["backend_url"], code1, room1_host_id, "Room 1 Current"
    )
    add_track_to_room(
        test_environment["backend_url"], code1, room1_host_id, "Room 1 Track"
    )
    add_track_to_room(
        test_environment["backend_url"], code2, room2_host_id, "Room 2 Current"
    )
    add_track_to_room(
        test_environment["backend_url"], code2, room2_host_id, "Room 2 Track"
    )

    room1_host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Room 1 Track",
    )
    room2_host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Room 2 Track",
    )

    assert queue_item(room1_host, "Room 1 Track").is_visible()
    assert queue_item(room1_guest, "Room 1 Track").is_visible()
    assert queue_item(room2_host, "Room 2 Track").is_visible()
    assert queue_item(room2_guest, "Room 2 Track").is_visible()

    assert room2_host.locator("text=Room 1 Track").count() == 0
    assert room2_guest.locator("text=Room 1 Track").count() == 0
    assert room1_host.locator("text=Room 2 Track").count() == 0
    assert room1_guest.locator("text=Room 2 Track").count() == 0

    context.close()


@pytest.mark.system
def test_sc19_users_in_different_rooms_dont_see_each_other(
    browser: Browser, test_environment
):
    """SC-19: Users in different rooms don't see each other."""
    context = browser.new_context()

    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Alice")

    room1_guest = context.new_page()
    join_room_helper(room1_guest, test_environment["frontend_url"], code1, "Bob")

    room2_host = context.new_page()
    code2 = create_room_helper(room2_host, test_environment["frontend_url"], "Charlie")

    room2_guest = context.new_page()
    join_room_helper(room2_guest, test_environment["frontend_url"], code2, "Diana")

    assert room1_host.locator("text=Alice").is_visible()
    assert room1_host.locator("text=Bob").is_visible()
    assert not room1_host.locator("text=Charlie").is_visible()
    assert not room1_host.locator("text=Diana").is_visible()

    assert room2_host.locator("text=Charlie").is_visible()
    assert room2_host.locator("text=Diana").is_visible()
    assert not room2_host.locator("text=Alice").is_visible()
    assert not room2_host.locator("text=Bob").is_visible()

    context.close()


@pytest.mark.system
def test_sc20_playback_in_one_room_doesnt_affect_other(
    browser: Browser, test_environment
):
    """SC-20: Playback in one room doesn't affect the other room."""
    context = browser.new_context()

    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Alice")

    room2_host = context.new_page()
    code2 = create_room_helper(room2_host, test_environment["frontend_url"], "Charlie")

    room1_state = get_room_state_snapshot(test_environment["backend_url"], code1)
    room1_host_id = user_id_for_display_name(room1_state, "Alice")

    room2_state = get_room_state_snapshot(test_environment["backend_url"], code2)
    room2_host_id = user_id_for_display_name(room2_state, "Charlie")

    add_track_to_room(
        test_environment["backend_url"], code1, room1_host_id, "Room 1 Track"
    )
    add_track_to_room(
        test_environment["backend_url"], code2, room2_host_id, "Room 2 Track"
    )

    send_room_event(
        test_environment["backend_url"],
        code1,
        {
            "type": "playback",
            "user_id": room1_host_id,
            "action": "resume",
        },
        expected_last_event="playback_updated",
    )

    room1_host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Pause",
    )
    assert (
        get_room_state_snapshot(test_environment["backend_url"], code1)["playback"][
            "state"
        ]
        == "playing"
    )

    assert room2_host.get_by_role("button", name="Resume").is_visible()
    assert room2_host.get_by_role("button", name="Pause").count() == 0
    assert (
        get_room_state_snapshot(test_environment["backend_url"], code2)["playback"][
            "state"
        ]
        == "paused"
    )

    context.close()


@pytest.mark.system
def test_sc21_votes_in_one_room_dont_affect_other(browser: Browser, test_environment):
    """SC-21: Votes in one room don't affect the queue in another room."""
    context = browser.new_context()

    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Alice")

    room1_guest = context.new_page()
    join_room_helper(room1_guest, test_environment["frontend_url"], code1, "Bob")

    room2_host = context.new_page()
    code2 = create_room_helper(room2_host, test_environment["frontend_url"], "Charlie")

    room2_guest = context.new_page()
    join_room_helper(room2_guest, test_environment["frontend_url"], code2, "Diana")

    room1_state = get_room_state_snapshot(test_environment["backend_url"], code1)
    room1_host_id = user_id_for_display_name(room1_state, "Alice")

    room2_state = get_room_state_snapshot(test_environment["backend_url"], code2)
    room2_host_id = user_id_for_display_name(room2_state, "Charlie")

    add_track_to_room(
        test_environment["backend_url"], code1, room1_host_id, "Room 1 Alpha"
    )
    add_track_to_room(
        test_environment["backend_url"], code1, room1_host_id, "Room 1 Beta"
    )
    add_track_to_room(
        test_environment["backend_url"], code2, room2_host_id, "Room 2 Alpha"
    )
    add_track_to_room(
        test_environment["backend_url"], code2, room2_host_id, "Room 2 Beta"
    )

    queue_item(room1_guest, "Room 1 Beta").get_by_role("button", name="Upvote").click()

    room1_host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score 1",
    )
    assert "Score 1" in queue_item(room1_host, "Room 1 Beta").inner_text()
    assert "Score 0" in queue_item(room2_host, "Room 2 Beta").inner_text()

    room2_host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score 0",
    )

    context.close()
