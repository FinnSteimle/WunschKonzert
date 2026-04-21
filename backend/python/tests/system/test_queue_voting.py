import pytest
from playwright.sync_api import Browser

from tests.system.conftest import add_song_helper, create_room_helper, join_room_helper


@pytest.mark.system
def test_sc5_add_song_to_queue_syncs_to_all(browser: Browser, test_environment):
    """SC-5: Song added to queue appears for all participants"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Host adds song
    add_song_helper(host, "Test Song")

    # Both see song in queue
    assert host.locator('[data-testid="queue-item"]', has_text="Test Song").is_visible(
        timeout=5000
    )
    assert guest.locator('[data-testid="queue-item"]', has_text="Test Song").is_visible(
        timeout=5000
    )

    context.close()


@pytest.mark.system
def test_sc6_upvote_reorders_queue(browser: Browser, test_environment):
    """SC-6: Upvoting a song reorders queue by vote score"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Host adds two songs
    add_song_helper(host, "Song A")
    add_song_helper(host, "Song B")

    # Verify initial order
    first_song = host.locator('[data-testid="queue-item"]:nth-child(1)').text_content()
    assert "Song A" in first_song

    # Guest upvotes Song B
    guest.locator('[data-testid="queue-item"]', has_text="Song B").locator(
        '[data-testid="upvote"]'
    ).click()

    # Verify Song B moved to top (higher vote score)
    first_song_after = host.locator(
        '[data-testid="queue-item"]:nth-child(1)'
    ).text_content(timeout=5000)
    assert "Song B" in first_song_after

    context.close()


@pytest.mark.system
def test_sc7_downvote_decreases_score(browser: Browser, test_environment):
    """SC-7: Downvoting a song decreases its vote score"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song
    add_song_helper(host, "Test Song")

    # Guest downvotes
    guest.locator('[data-testid="queue-item"]', has_text="Test Song").locator(
        '[data-testid="downvote"]'
    ).click()

    # Verify vote score decreased
    vote_score = (
        host.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="vote-score"]')
        .text_content(timeout=5000)
    )
    assert "-1" in vote_score

    context.close()


@pytest.mark.system
def test_sc8_user_can_change_vote(browser: Browser, test_environment):
    """SC-8: User can change their vote from upvote to downvote"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest = context.new_page()
    join_room_helper(guest, test_environment["frontend_url"], join_code, "Guest")

    # Add song
    add_song_helper(host, "Test Song")

    # Guest upvotes
    song_item = guest.locator('[data-testid="queue-item"]', has_text="Test Song")
    song_item.locator('[data-testid="upvote"]').click()

    # Verify score is +1
    vote_score = (
        host.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="vote-score"]')
        .text_content(timeout=5000)
    )
    assert "1" in vote_score

    # Guest changes to downvote
    song_item.locator('[data-testid="downvote"]').click()

    # Verify score changed to -1
    vote_score_after = (
        host.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="vote-score"]')
        .text_content(timeout=5000)
    )
    assert "-1" in vote_score_after

    context.close()


@pytest.mark.system
def test_sc9_multiple_users_vote_aggregates(browser: Browser, test_environment):
    """SC-9: Multiple users voting aggregates correctly"""
    context = browser.new_context()

    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")

    guest1 = context.new_page()
    join_room_helper(guest1, test_environment["frontend_url"], join_code, "Guest1")

    guest2 = context.new_page()
    join_room_helper(guest2, test_environment["frontend_url"], join_code, "Guest2")

    # Add song
    add_song_helper(host, "Test Song")

    # All upvote
    guest1.locator('[data-testid="queue-item"]', has_text="Test Song").locator(
        '[data-testid="upvote"]'
    ).click()
    guest2.locator('[data-testid="queue-item"]', has_text="Test Song").locator(
        '[data-testid="upvote"]'
    ).click()

    # Verify aggregated score
    vote_score = (
        host.locator('[data-testid="queue-item"]', has_text="Test Song")
        .locator('[data-testid="vote-score"]')
        .text_content(timeout=5000)
    )
    assert "2" in vote_score

    context.close()
