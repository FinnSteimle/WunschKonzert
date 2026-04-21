import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


@pytest.mark.system
def test_sc19_concurrent_rooms_remain_isolated(browser: Browser, test_environment):
    """SC-19: Multiple concurrent rooms don't interfere with each other"""
    context = browser.new_context()

    # Create two separate rooms
    room1_host = context.new_page()
    create_room_helper(room1_host, test_environment["frontend_url"], "Room1Host")

    room2_host = context.new_page()
    create_room_helper(room2_host, test_environment["frontend_url"], "Room2Host")

    # Add different songs to each room
    add_song_helper(room1_host, "Room 1 Song")
    add_song_helper(room2_host, "Room 2 Song")

    # Verify isolation - Room 1 only sees its song
    assert room1_host.locator(
        '[data-testid="queue-item"]', has_text="Room 1 Song"
    ).is_visible()
    assert not room1_host.locator(
        '[data-testid="queue-item"]', has_text="Room 2 Song"
    ).is_visible()

    # Verify isolation - Room 2 only sees its song
    assert room2_host.locator(
        '[data-testid="queue-item"]', has_text="Room 2 Song"
    ).is_visible()
    assert not room2_host.locator(
        '[data-testid="queue-item"]', has_text="Room 1 Song"
    ).is_visible()

    context.close()


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


@pytest.mark.system
def test_sc21_playback_in_one_room_doesnt_affect_other(
    browser: Browser, test_environment
):
    """SC-21: Playback in one room doesn't affect other rooms"""
    context = browser.new_context()

    # Room 1
    room1_host = context.new_page()
    create_room_helper(room1_host, test_environment["frontend_url"], "Host1")
    add_song_helper(room1_host, "Song 1")

    # Room 2
    room2_host = context.new_page()
    create_room_helper(room2_host, test_environment["frontend_url"], "Host2")
    add_song_helper(room2_host, "Song 2")

    # Room 1 starts playback
    room1_host.click('[data-testid="play-button"]')

    # Room 1 is playing
    assert (
        room1_host.locator('[data-testid="playback-state"]').text_content(timeout=5000)
        == "playing"
    )

    # Room 2 is still paused
    assert (
        room2_host.locator('[data-testid="playback-state"]').text_content() == "paused"
    )

    context.close()


@pytest.mark.system
def test_sc22_votes_in_one_room_dont_affect_other(browser: Browser, test_environment):
    """SC-22: Votes in one room don't affect queue in other rooms"""
    context = browser.new_context()

    # Room 1
    room1_host = context.new_page()
    code1 = create_room_helper(room1_host, test_environment["frontend_url"], "Host1")

    room1_guest = context.new_page()
    join_room_helper(room1_guest, test_environment["frontend_url"], code1, "Guest1")

    add_song_helper(room1_host, "Shared Song Name")

    # Room 2
    room2_host = context.new_page()
    create_room_helper(room2_host, test_environment["frontend_url"], "Host2")
    add_song_helper(room2_host, "Shared Song Name")

    # Room 1 guest upvotes
    room1_guest.locator(
        '[data-testid="queue-item"]', has_text="Shared Song Name"
    ).locator('[data-testid="upvote"]').click()

    # Room 1 shows vote score of 1
    room1_score = (
        room1_host.locator('[data-testid="queue-item"]', has_text="Shared Song Name")
        .locator('[data-testid="vote-score"]')
        .text_content(timeout=5000)
    )
    assert "1" in room1_score

    # Room 2 still shows vote score of 0
    room2_score = (
        room2_host.locator('[data-testid="queue-item"]', has_text="Shared Song Name")
        .locator('[data-testid="vote-score"]')
        .text_content()
    )
    assert "0" in room2_score

    context.close()
