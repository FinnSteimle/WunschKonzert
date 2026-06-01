# System Tests

End-to-end tests for WunschKonzert driven by Playwright. They exercise the full stack — SvelteKit frontend, FastAPI backend, PostgreSQL, and the room WebSocket — through a real browser.

## Layout

```text
tests/system/
├── conftest.py                 # Fixtures, helpers, page objects
├── test_room_lifecycle.py      # Create / join / leave / refresh (SC-1…SC-4)
├── test_queue_voting.py        # Add tracks, vote, reordering (SC-5…SC-9)
├── test_playback_sync.py       # Play / pause / position sync (SC-10…SC-14)
├── test_host_controls.py       # Host-only operations (SC-15…SC-17)
├── test_host_transfer.py       # Host-transfer handshake (SC-22…SC-23)
├── test_concurrent_rooms.py    # Multi-room isolation (SC-18…SC-21)
├── test_responsive_design.py   # Cross-browser layout (WUN-91)
└── test_stack_mapping.py       # Maps verified scenarios to the trace matrix
```

## Running

The standard entry point is the Makefile target, which orchestrates `compose.yaml` + `compose.system.yaml`, waits for backend + frontend health, and runs the suite inside the API container:

```bash
make test-system
```

`make test-system` leaves the stack running on success. Use `make clean` to tear it down.

### Test environment

`compose.system.yaml` overrides the URLs so the browser and backend talk to each other through Docker service DNS:

- `PUBLIC_API_URL=http://api:8000`
- `PUBLIC_WS_URL=ws://api:8000`
- Playwright fixtures expect `FRONTEND_URL=http://frontend:3000`, `BACKEND_URL=http://api:8000`

These URLs are also injected as **build args** so the bundled client uses the same mapping inside the test image.

Spotify search and token calls are redirected to a local mock service, so tests don't hit the real Spotify API and stay deterministic. Queue / vote / playback / multi-room tests seed tracks directly through the room WebSocket for the same reason.

### Targeted runs

Run a single file or test inside the running stack:

```bash
docker compose exec api uv run pytest tests/system/test_room_lifecycle.py -v
docker compose exec api uv run pytest tests/system/test_room_lifecycle.py::test_sc1_host_creates_room_guest_joins -v
```

Run with a headed browser for debugging (requires a display forwarded to the container):

```bash
docker compose exec api uv run pytest tests/system/ -v --headed
```

## Debugging Infos

- `--headed` shows the browser.
- `page.pause()` drops into the Playwright inspector.
- Failure screenshots and traces land in `test-results/`.
- `page.screenshot(path="debug.png")` for ad-hoc captures.
- The frontend exposes `data-testid` attributes on every element the suite interacts with — keep these stable when refactoring components.
