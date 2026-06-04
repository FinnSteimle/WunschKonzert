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


def wait_for_queue_order(page: Page, first_title: str, second_title: str) -> None:
    page.wait_for_function(
        """
        ([firstTitle, secondTitle]) => {
            const list = document.querySelector('[aria-label="Playback queue"]');
            if (!list) return false;
            const items = Array.from(list.querySelectorAll('li'));
            return (
                items.length >= 2 &&
                items[0].innerText.includes(firstTitle) &&
                items[1].innerText.includes(secondTitle)
            );
        }
        """,
        arg=[first_title, second_title],
    )


@pytest.mark.system
def test_sc5_add_song_to_queue_syncs_to_all(browser: Browser, test_environment):
    """SC-5: Song added to queue appears for all participants."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")
    guest_id = user_id_for_display_name(room_state, "Guest")

    add_track_to_room(
        test_environment["backend_url"], join_code, host_id, "Warmup Track"
    )
    add_track_to_room(
        test_environment["backend_url"], join_code, guest_id, "Visible Queue Track"
    )

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Visible Queue Track",
    )
    guest.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Visible Queue Track",
    )

    assert queue_item(host, "Visible Queue Track").is_visible()
    assert queue_item(guest, "Visible Queue Track").is_visible()

    context.close()


@pytest.mark.system
def test_sc6_upvote_reorders_queue(browser: Browser, test_environment):
    """SC-6: Upvoting a song reorders queue by vote score."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Alpha")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Beta")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Gamma")

    wait_for_queue_order(host, "Beta", "Gamma")
    wait_for_queue_order(guest, "Beta", "Gamma")

    queue_item(guest, "Gamma").get_by_role("button", name="Upvote").click()

    wait_for_queue_order(host, "Gamma", "Beta")
    wait_for_queue_order(guest, "Gamma", "Beta")

    context.close()


@pytest.mark.system
def test_sc7_downvote_decreases_score(browser: Browser, test_environment):
    """SC-7: Downvoting a song decreases its visible vote score."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Alpha")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Beta")

    queue_item(guest, "Beta").get_by_role("button", name="Downvote").click()

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score -1",
    )
    assert "Score -1" in queue_item(host, "Beta").inner_text()

    context.close()


@pytest.mark.system
def test_sc8_user_can_change_vote(browser: Browser, test_environment):
    """SC-8: User can switch from upvote to downvote and the score updates."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Alpha")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Beta")

    beta_item = queue_item(guest, "Beta")
    beta_item.get_by_role("button", name="Upvote").click()
    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score 1",
    )
    assert "Score 1" in queue_item(host, "Beta").inner_text()

    beta_item.get_by_role("button", name="Downvote").click()
    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score -1",
    )
    assert "Score -1" in queue_item(host, "Beta").inner_text()

    context.close()


@pytest.mark.system
def test_sc9_multiple_users_vote_aggregates(browser: Browser, test_environment):
    """SC-9: Upvotes from multiple users combine into the visible score."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest1 = context.new_page()
    join_room_helper(guest1, test_environment["frontend_url"], join_code, "Guest 1")

    guest2 = context.new_page()
    join_room_helper(guest2, test_environment["frontend_url"], join_code, "Guest 2")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")

    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Alpha")
    add_track_to_room(test_environment["backend_url"], join_code, host_id, "Beta")

    queue_item(guest1, "Beta").get_by_role("button", name="Upvote").click()
    queue_item(guest2, "Beta").get_by_role("button", name="Upvote").click()

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Score 2",
    )
    assert "Score 2" in queue_item(host, "Beta").inner_text()

    context.close()
