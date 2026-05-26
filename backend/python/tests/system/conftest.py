import json
import os
import time
import uuid
from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from threading import Thread

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from websockets.sync.client import connect

from models.domain import AccountStatus, ProviderAccount, User
from repositories import room_repo

USER_ID_KEY = "wk_user_id"
DISPLAY_NAME_KEY = "wk_display_name"


@pytest.fixture(scope="session")
def test_environment():
    """Test environment URLs - assumes services are running via docker compose"""
    return {
        "backend_url": os.getenv("BACKEND_URL", "http://localhost:8000"),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000"),
    }


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Browser:
    """Launch browser for the test session"""
    browser = playwright.chromium.launch(headless=True)
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
    user_id, _ = set_session_identity(page, frontend_url, display_name)
    page.goto(
        f"{frontend_url}/create?spotify_linked=true", wait_until="domcontentloaded"
    )
    page.wait_for_selector('input[name="displayName"]', state="visible")
    page.wait_for_selector('input[name="name"]', state="visible")
    # System tests run inside pytest's async environment, so run DB seeding in a
    # separate thread with its own event loop instead of calling asyncio.run()
    # from the test thread.
    run_async_in_thread(
        seed_spotify_link_for_user(
            user_id=user_id,
            display_name=display_name,
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
    page.wait_for_selector('ul[aria-label="Room members"]', state="visible")
    page.wait_for_selector("#wk-search", state="visible")
    room_path = page.url.split("/room/")[-1]
    return room_path.strip().upper()


def join_room_helper(page: Page, frontend_url: str, join_code: str, display_name: str):
    """Helper to join a room"""
    _, previous_identity = set_session_identity(page, frontend_url, display_name)
    page.goto(f"{frontend_url}/room/{join_code}", wait_until="domcontentloaded")
    join_prompt = page.locator('input[name="displayName"]')
    if join_prompt.is_visible(timeout=1000):
        page.fill('input[name="displayName"]', display_name)
        page.click('button:has-text("Join room")')
    page.wait_for_selector("text=Who is here", state="visible")
    restore_session_identity(page, previous_identity)


def add_song_helper(page: Page, song_name: str):
    """Helper to search and add a song to queue"""
    page.wait_for_selector("#wk-search", state="visible")
    page.locator("#wk-search").fill(song_name)
    page.get_by_role("button", name="Search").click()
    page.get_by_role("list", name="Search results").wait_for(state="visible")
    page.get_by_role("list", name="Search results").get_by_role(
        "button", name="Add to queue"
    ).first.click()


def backend_ws_url(backend_url: str) -> str:
    """Translate an HTTP backend URL into the matching WebSocket URL."""
    if backend_url.startswith("https://"):
        return "wss://" + backend_url.removeprefix("https://")
    if backend_url.startswith("http://"):
        return "ws://" + backend_url.removeprefix("http://")
    return backend_url.replace("http://", "ws://", 1)


def room_ws_url(backend_url: str, room_id: str) -> str:
    return f"{backend_ws_url(backend_url)}/ws/{room_id}"


def _is_join_code(value: str) -> bool:
    return len(value) == 6 and value.isalnum() and value.upper() == value


def resolve_room_reference(backend_url: str, room_ref: str) -> str:
    """Resolve a join code to the backend room UUID when needed."""
    if not _is_join_code(room_ref):
        return room_ref

    database_url = os.environ["DATABASE_URL"]
    if not database_url.startswith("postgresql+asyncpg://"):
        if "://" in database_url:
            _, base_url = database_url.split("://", 1)
            database_url = f"postgresql+asyncpg://{base_url}"
        else:
            database_url = f"postgresql+asyncpg://{database_url}"

    async def _lookup() -> str:
        engine = create_async_engine(
            database_url,
            poolclass=NullPool,
            pool_pre_ping=True,
        )
        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with session_factory() as session:
                room = await room_repo.get_room_by_join_code(room_ref, session=session)
                return room.roomId
        finally:
            await engine.dispose()

    return run_async_in_thread(_lookup())


def receive_room_state(ws, timeout: float = 5.0) -> dict[str, object]:
    """Receive the next JSON room-state payload from a room websocket."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = max(0.1, deadline - time.monotonic())
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for room state")
        message = ws.recv(timeout=remaining)
        if message == "ping":
            continue
        return json.loads(message)


def get_room_state_snapshot(
    backend_url: str, room_id: str, timeout: float = 5.0
) -> dict[str, object]:
    """Open a short-lived websocket connection and capture the current room state."""
    resolved_room_id = resolve_room_reference(backend_url, room_id)
    with connect(
        room_ws_url(backend_url, resolved_room_id),
        open_timeout=timeout,
        close_timeout=timeout,
        ping_interval=None,
    ) as ws:
        return receive_room_state(ws, timeout=timeout)


def send_room_event(
    backend_url: str,
    room_id: str,
    event: dict[str, object],
    expected_last_event: str | None = None,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Send a websocket event to a live room and return the resulting room state."""
    resolved_room_id = resolve_room_reference(backend_url, room_id)
    with connect(
        room_ws_url(backend_url, resolved_room_id),
        open_timeout=timeout,
        close_timeout=timeout,
        ping_interval=None,
    ) as ws:
        receive_room_state(ws, timeout=timeout)
        ws.send(json.dumps(event))

        deadline = time.monotonic() + timeout
        last_state: dict[str, object] | None = None
        while True:
            remaining = max(0.1, deadline - time.monotonic())
            if remaining <= 0:
                raise TimeoutError(
                    f"Timed out waiting for room event {expected_last_event or event.get('type')}"
                )

            message = ws.recv(timeout=remaining)
            if message == "ping":
                continue

            last_state = json.loads(message)
            last_event = last_state.get("lastEvent")
            if expected_last_event is None or (
                isinstance(last_event, dict)
                and last_event.get("type") == expected_last_event
            ):
                return last_state

        raise TimeoutError("Timed out waiting for room event state")


def user_id_for_display_name(room_state: dict[str, object], display_name: str) -> str:
    """Look up a room member's userId from a captured room-state payload."""
    if room_state.get("host", {}).get("displayName") == display_name:
        return str(room_state["host"]["userId"])

    for member in room_state.get("users", []):
        if not isinstance(member, dict):
            continue
        user = member.get("user")
        if isinstance(user, dict) and user.get("displayName") == display_name:
            return str(user["userId"])

    raise AssertionError(f"Display name {display_name!r} not found in room state")


def parse_elapsed_seconds(playback_text: str) -> int:
    """Parse the elapsed playback label shown by PlaybackProgress."""
    first_line = playback_text.strip().splitlines()[0]
    minutes, seconds = first_line.split(":")
    return int(minutes) * 60 + int(seconds)


def make_track_payload(
    title: str,
    artist: str = "Artist",
    *,
    track_id: str | None = None,
    provider_track_id: str | None = None,
) -> dict[str, object]:
    """Build a minimal track payload accepted by the add-to-queue websocket event."""
    track_id = track_id or f"track-{uuid.uuid4().hex[:8]}"
    provider_track_id = provider_track_id or f"spotify:track:{track_id[:8]}"
    return {
        "trackId": track_id,
        "providerTrackId": provider_track_id,
        "title": title,
        "artist": artist,
        "album": "",
        "duration": 180,
        "coverUrl": "",
        "deepLink": "",
    }


def add_track_to_room(
    backend_url: str,
    room_id: str,
    user_id: str,
    title: str,
    *,
    artist: str = "Artist",
) -> tuple[dict[str, object], str]:
    """Add a track via websocket and return the updated room state plus queueEntryId."""
    state = send_room_event(
        backend_url,
        room_id,
        {
            "type": "addqueue",
            "track": make_track_payload(title, artist),
            "user_id": user_id,
        },
        expected_last_event="queue_updated",
    )
    queue = state.get("queue", [])
    if not isinstance(queue, list):
        raise AssertionError("Room state queue payload is missing")

    for entry in queue:
        if isinstance(entry, dict):
            track = entry.get("track")
            if isinstance(track, dict) and track.get("title") == title:
                return state, str(entry["queueEntryId"])

    raise AssertionError(f"Track {title!r} not found in queue state")


def run_async_in_thread(coro):
    """Run a coroutine in an isolated thread for sync Playwright helpers."""
    result: Future = Future()

    def target():
        import asyncio

        try:
            result.set_result(asyncio.run(coro))
        except BaseException as exc:
            result.set_exception(exc)

    thread = Thread(target=target, daemon=True)
    thread.start()
    thread.join()
    return result.result()


def set_session_identity(
    page: Page, frontend_url: str, display_name: str
) -> tuple[str, dict[str, str | None]]:
    """Seed a deterministic browser identity before the app reads localStorage."""
    user_id = f"U_{uuid.uuid4().hex[:10].upper()}"
    page.goto(frontend_url, wait_until="domcontentloaded")
    previous_identity = page.evaluate(
        f"""
        () => {{
            const previous = {{
                userId: localStorage.getItem('{USER_ID_KEY}'),
                displayName: localStorage.getItem('{DISPLAY_NAME_KEY}')
            }};
            localStorage.setItem('{USER_ID_KEY}', '{user_id}');
            localStorage.setItem('{DISPLAY_NAME_KEY}', {display_name!r});
            return previous;
        }}
        """
    )
    return user_id, previous_identity


def restore_session_identity(page: Page, identity: dict[str, str | None]) -> None:
    """Restore shared localStorage for other pages in the same browser context."""
    page.evaluate(
        f"""
        (identity) => {{
            if (identity.userId) localStorage.setItem('{USER_ID_KEY}', identity.userId);
            else localStorage.removeItem('{USER_ID_KEY}');

            if (identity.displayName) localStorage.setItem('{DISPLAY_NAME_KEY}', identity.displayName);
            else localStorage.removeItem('{DISPLAY_NAME_KEY}');
        }}
        """,
        identity,
    )


async def seed_spotify_link_for_user(
    user_id: str,
    display_name: str,
    provider_id: str,
    external_user_id: str,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime,
):
    """Seed the minimum backend state the create-room flow requires."""
    database_url = os.environ["DATABASE_URL"]
    if not database_url.startswith("postgresql+asyncpg://"):
        if "://" in database_url:
            _, base_url = database_url.split("://", 1)
            database_url = f"postgresql+asyncpg://{base_url}"
        else:
            database_url = f"postgresql+asyncpg://{database_url}"
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                session.add(User(userId=user_id, displayName=display_name))
                await session.flush()

            result = await session.execute(
                select(ProviderAccount).where(
                    ProviderAccount.userId == user_id,
                    ProviderAccount.providerId == provider_id,
                )
            )
            provider_account = result.scalar_one_or_none()

            if provider_account is None:
                provider_account = ProviderAccount(
                    providerAccountId=str(uuid.uuid4()),
                    externalUserId=external_user_id,
                    userId=user_id,
                    providerId=provider_id,
                    status=AccountStatus.ACTIVE,
                    accessToken=access_token,
                    refreshToken=refresh_token,
                    tokenExpiresAt=token_expires_at,
                )
                session.add(provider_account)
            else:
                provider_account.externalUserId = external_user_id
                provider_account.status = AccountStatus.ACTIVE
                provider_account.accessToken = access_token
                provider_account.refreshToken = refresh_token
                provider_account.tokenExpiresAt = token_expires_at

            await session.commit()
    finally:
        await engine.dispose()
