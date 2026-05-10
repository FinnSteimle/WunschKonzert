import os

import pytest

from tests.system.conftest import create_room_helper

# Define the matrix of engines and viewports
TEST_MATRIX = [
    {
        "name": "chromium-mobile",
        "browser": "chromium",
        "viewport": {"width": 320, "height": 568},
        "is_mobile": True,
    },
    {
        "name": "firefox-mobile",
        "browser": "firefox",
        "viewport": {"width": 320, "height": 568},
        "is_mobile": True,
    },
    {
        "name": "webkit-mobile",
        "browser": "webkit",
        "viewport": {"width": 320, "height": 568},
        "is_mobile": True,
    },
    {
        "name": "chromium-desktop",
        "browser": "chromium",
        "viewport": {"width": 1280, "height": 720},
        "is_mobile": False,
    },
    {
        "name": "firefox-desktop",
        "browser": "firefox",
        "viewport": {"width": 1280, "height": 720},
        "is_mobile": False,
    },
    {
        "name": "webkit-desktop",
        "browser": "webkit",
        "viewport": {"width": 1280, "height": 720},
        "is_mobile": False,
    },
]


@pytest.mark.system
@pytest.mark.parametrize("config", TEST_MATRIX)
def test_cross_browser_responsive_verification(config, test_environment, playwright):
    """WUN-91: Comprehensive Cross-Browser and Responsive Verification"""
    # 1. Launch the specific browser engine
    browser_type = getattr(playwright, config["browser"])
    browser = browser_type.launch(headless=True)

    # 2. Setup context with mobile emulation if needed
    context_args = {
        "viewport": config["viewport"],
    }
    if config["is_mobile"]:
        # Use a standard iPhone SE user agent for all mobile tests to ensure parity
        context_args["user_agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1"
        )
        context_args["has_touch"] = True

    context = browser.new_context(**context_args)
    page = context.new_page()

    frontend_url = test_environment["frontend_url"]
    screenshots_dir = f"/app/screenshots/{config['name']}"
    os.makedirs(screenshots_dir, exist_ok=True)

    try:
        # --- PHASE 1: Landing Page ---
        page.goto(frontend_url, wait_until="networkidle")
        page.screenshot(path=f"{screenshots_dir}/01_home.png")
        assert page.locator("text=WunschKonzert").is_visible()
        assert page.locator(':is(button, a):has-text("Create")').is_visible()

        # --- PHASE 2: Create Room ---
        page.goto(f"{frontend_url}/create", wait_until="networkidle")
        page.screenshot(path=f"{screenshots_dir}/02_create.png")
        assert page.locator('input[name="displayName"]').is_visible()

        # --- PHASE 3: Room View & Interaction ---
        # create_room_helper handles seeding and navigation
        join_code = create_room_helper(page, frontend_url, f"User-{config['browser']}")
        page.wait_for_selector("text=Who is here", state="visible")
        page.screenshot(path=f"{screenshots_dir}/03_room.png")

        # Verify key room elements
        assert page.locator(f"text={join_code}").is_visible()
        # The heading we fixed earlier
        assert page.locator("#wk-search-heading").is_visible()

        # Check for horizontal scroll
        scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
        client_width = page.evaluate("() => document.documentElement.clientWidth")
        assert scroll_width <= client_width, (
            f"Horizontal scroll detected on {config['name']}: {scroll_width} > {client_width}"
        )

    finally:
        browser.close()
