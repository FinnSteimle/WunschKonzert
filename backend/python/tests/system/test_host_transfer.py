from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import Browser, Page

from tests.system.conftest import (
    create_room_helper,
    get_room_state_snapshot,
    join_room_helper,
    run_async_in_thread,
    seed_spotify_link_for_user,
    user_id_for_display_name,
)


def member_item(page: Page, name: str):
    return (
        page.get_by_role("list", name="Room members")
        .get_by_role("listitem")
        .filter(has_text=name)
    )


@pytest.mark.system
def test_sc22_guest_can_accept_host_transfer(browser: Browser, test_environment):
    """SC-22: Host can transfer ownership and the invitee can accept."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")
    guest_id = user_id_for_display_name(room_state, "Guest")

    run_async_in_thread(
        seed_spotify_link_for_user(
            user_id=guest_id,
            display_name="Guest",
            provider_id="spotify",
            external_user_id=f"spotify-{guest_id}",
            access_token="system-test-access-token",
            refresh_token="system-test-refresh-token",
            token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )

    member_item(host, "Guest").get_by_role("button", name="Make host").click()

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Host transfer pending",
    )
    guest.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Host invitation",
    )

    assert guest.get_by_role("button", name="Accept host role").is_enabled()
    guest.get_by_role("button", name="Accept host role").click()

    host.wait_for_function(
        """
        () => {
            const text = document.body.innerText;
            return !text.includes('Delete room') && text.includes('Leave room');
        }
        """
    )
    guest.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Delete room",
    )

    updated_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    assert updated_state["host"]["userId"] == guest_id
    assert updated_state["host"]["userId"] != host_id
    assert updated_state.get("transfer") is None

    assert host.get_by_role("button", name="Delete room").count() == 0
    assert guest.get_by_role("button", name="Delete room").is_visible()

    context.close()


@pytest.mark.system
def test_sc23_guest_can_decline_host_transfer(browser: Browser, test_environment):
    """SC-23: Host can transfer ownership and the invitee can decline."""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    room_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    host_id = user_id_for_display_name(room_state, "Host")
    guest_id = user_id_for_display_name(room_state, "Guest")

    member_item(host, "Guest").get_by_role("button", name="Make host").click()

    host.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Host transfer pending",
    )
    guest.wait_for_function(
        "needle => document.body.innerText.includes(needle)",
        arg="Host invitation",
    )

    guest.get_by_role("button", name="Decline").click()

    host.wait_for_function(
        """
        () => {
            const text = document.body.innerText;
            return !text.includes('Host transfer pending');
        }
        """
    )
    guest.wait_for_function(
        """
        () => {
            const text = document.body.innerText;
            return !text.includes('Host invitation');
        }
        """
    )

    updated_state = get_room_state_snapshot(test_environment["backend_url"], join_code)
    assert updated_state["host"]["userId"] == host_id
    assert updated_state["host"]["userId"] != guest_id
    assert updated_state.get("transfer") is None

    assert host.get_by_role("button", name="Delete room").is_visible()
    assert guest.get_by_role("button", name="Delete room").count() == 0

    context.close()
