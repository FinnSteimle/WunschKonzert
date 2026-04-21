import os
from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

import repositories.crud as crud


@pytest.fixture(scope="session")
def test_environment():
    """Test environment URLs - assumes services are running via docker compose"""
    return {
        "backend_url": os.getenv("BACKEND_URL", "http://localhost:8000"),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000"),
    }


@pytest.fixture(scope="session")
def browser():
    """Launch browser for the test session"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser: Browser) -> BrowserContext:
    """Create a new browser context for each test"""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    """Create a new page for each test"""
    page = context.new_page()
    yield page
    page.close()


def create_room_helper(
    page: Page, frontend_url: str, display_name: str = "Host"
) -> str:
    """Helper to create a room and return join code"""
    page.goto(f"{frontend_url}/create?spotify_linked=true", wait_until="domcontentloaded")
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.wait_for_selector('input[name="name"]', state="visible")
    user_id = page.evaluate(
        """
        () => {
            const key = 'wk_user_id';
            let userId = localStorage.getItem(key);
            if (!userId) {
                userId = `U_TEST_${Math.random().toString(36).slice(2, 12).toUpperCase()}`;
                localStorage.setItem(key, userId);
            }
            return userId;
        }
        """
    )
    # System tests run without real OAuth; seed a provider account token for this browser user.
    import asyncio

    asyncio.run(
        crud.create_or_update_provider_account_tokens(
            user_id=user_id,
            provider_id="spotify",
            external_user_id=f"spotify-{user_id}",
            access_token="system-test-access-token",
            refresh_token="system-test-refresh-token",
            token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    page.fill('input[name="displayName"]', display_name)
    page.fill('input[name="name"]', "Test Room")
    page.click('button:has-text("Create room")')
    page.wait_for_function("() => window.location.pathname.includes('/room/')")
    room_path = page.url.split("/room/")[-1]
    return room_path.strip().upper()


def join_room_helper(page: Page, frontend_url: str, join_code: str, display_name: str):
    """Helper to join a room"""
    page.goto(f"{frontend_url}/room/{join_code}", wait_until="domcontentloaded")
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.fill('input[name="displayName"]', display_name)
    page.click('button:has-text("Join room")')
    page.wait_for_function("() => window.location.pathname.includes('/room/')")


def add_song_helper(page: Page, song_name: str):
    """Helper to search and add a song to queue"""
    page.fill('[data-testid="search-input"]', song_name)
    page.wait_for_selector('[data-testid="search-result-0"]')
    page.click('[data-testid="search-result-0"] button')
