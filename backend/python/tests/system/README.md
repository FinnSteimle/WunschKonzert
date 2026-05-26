# System Tests

End-to-end system tests for WunschKonzert using Playwright to verify full-stack functionality.

## Overview

System tests verify complete user workflows across the entire stack:
- Frontend (SvelteKit)
- Backend (FastAPI + WebSocket)
- Database (PostgreSQL)
- Real-time synchronization

## Test Structure

```
tests/system/
├── conftest.py              # Fixtures and helper functions
├── test_room_lifecycle.py   # Room creation, joining, leaving
├── test_queue_voting.py     # Queue management and voting
├── test_playback_sync.py    # Playback synchronization
├── test_host_controls.py    # Host-only operations
├── test_host_transfer.py    # Host transfer workflow
├── test_concurrent_rooms.py # Multi-room isolation
└── test_responsive_design.py # Cross-browser responsive layout
```

## Prerequisites

1. Install Playwright:
```bash
cd backend
uv add --dev playwright pytest-playwright
uv run playwright install chromium
```

2. Ensure services are running:
```bash
make run
```

## Running Tests

Run all system tests:
```bash
make test-system
```

`make test-system` uses `compose.system.yaml` so the frontend always targets the backend
through Docker service DNS during system tests:

- `PUBLIC_API_URL=http://api:8000`
- `PUBLIC_WS_URL=ws://api:8000`
- Playwright test fixture URLs:
  - `FRONTEND_URL=http://frontend:3000`
  - `BACKEND_URL=http://api:8000`

The frontend URLs are injected as Docker **build args** (not only runtime env), so
the bundled client code uses the same mapping during tests.

System-test Docker runs route Spotify search/token calls to a dedicated local
mock service, so song search uses deterministic stub results instead of live
Spotify HTTP calls.

Queue, voting, playback, and multi-room tests seed tracks directly through the
room WebSocket so they stay deterministic without depending on the search UI.

`make test-system` executes the full `tests/system/` suite under Docker.

Run specific test file:
```bash
docker compose exec api uv run pytest tests/system/test_room_lifecycle.py -v
```

Run specific test:
```bash
docker compose exec api uv run pytest tests/system/test_room_lifecycle.py::test_sc1_host_creates_room_guest_joins -v
```

Run with headed browser (for debugging):
```bash
docker compose exec api uv run pytest tests/system/ -v --headed
```

## Test Scenarios

### Room Lifecycle (SC-1 to SC-4)
- Host creates room, guest joins
- Guest leaves, host sees update
- Invalid join code handling
- Room state persistence after refresh

### Queue & Voting (SC-5 to SC-9)
- Add songs to queue
- Upvote/downvote songs
- Vote aggregation
- Queue reordering by score

### Playback Sync (SC-10 to SC-14)
- Start/pause playback
- Playback state synchronization
- Host-only controls
- Advance to next song
- Position synchronization

### Host Controls (SC-15 to SC-17)
- Delete room (host only)
- Remove songs from queue
- User removes own song

### Host Transfer (SC-22 to SC-23)
- Offer host transfer
- Accept host transfer after provider linking
- Decline a pending host transfer
- Host ownership changes in real time

### Concurrent Rooms (SC-18 to SC-21)
- Room isolation
- User isolation
- Playback isolation
- Vote isolation

### Responsive Design (WUN-91)
- Cross-browser layout verification at mobile and desktop breakpoints

## Writing New Tests

1. Add test to appropriate file or create new file
2. Use helper functions from `conftest.py`:
   - `create_room_helper()` - Create room and return join code
   - `join_room_helper()` - Join existing room
   - `add_song_helper()` - Search and add song to queue

3. Mark test with `@pytest.mark.system`

Example:
```python
@pytest.mark.system
def test_my_feature(browser: Browser, test_environment):
    context = browser.new_context()
    
    host = context.new_page()
    join_code = create_room_helper(host, test_environment["frontend_url"], "Host")
    
    # Your test logic here
    
    context.close()
```

## CI/CD Integration

System tests can be added to GitLab CI:

```yaml
system_test:
  stage: e2e
  script:
    - make test-system
  artifacts:
    when: on_failure
    paths:
      - test-results/
      - playwright-report/
```

## Debugging

- Use `--headed` flag to see browser
- Add `page.pause()` to pause execution
- Check screenshots in `test-results/` on failure
- Use `page.screenshot(path="debug.png")` for manual screenshots

## Notes

- Tests assume frontend uses specific `data-testid` attributes
- Frontend components must be updated to include these test IDs
- Tests run in isolated browser contexts
- Each test creates fresh browser context for isolation
