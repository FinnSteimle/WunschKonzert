# WunschKonzert

A collaborative music room application: users join a room, suggest songs, vote on what plays next, and listen together in real time with synchronized playback across all participants.

Built as the SE-Project (g15) at OST, FS 2026.

## Architecture

| Layer | Technology |
|---|---|
| Frontend | Svelte 5 + SvelteKit, TailwindCSS 4, shadcn-svelte |
| Backend | FastAPI on Python 3.14+, SQLAlchemy 2.0 (async), WebSockets |
| Database | PostgreSQL, migrations managed with Alembic |
| Music providers | Spotify OAuth 2.0, Apple Music (MusicKit JWT) |
| Reverse proxy / TLS | Caddy (TLS 1.2+) |
| Containerization | Docker + Docker Compose |

## Project Structure

```text
.
├── backend/python/        # FastAPI service: api, services, repositories, models, migrations, tests
├── frontend/              # SvelteKit application
├── scripts/               # CI helpers, NFR verification scripts
├── load-tests/            # k6 capacity & scalability tests
├── compose.yaml           # Local dev orchestration
├── compose.system.yaml    # System-test overlay (Playwright)
├── compose.staging.yaml   # Staging deployment
├── compose.prod.yaml      # Production deployment
├── Caddyfile              # Reverse-proxy / TLS configuration
├── DEPLOYMENT.md          # Deployment runbook
├── MANUAL_QA.md           # Manual QA checklist
└── Makefile               # Entry point for all dev workflows
```

## Quick Start

```bash
git clone https://gitlab.ost.ch/SEProj/2026-FS/g15-wunschkonzert/wunschkonzert.git
cd wunschkonzert
cp backend/.env.example backend/.env      # then fill in Spotify credentials
cp frontend/.env.example frontend/.env
make run
```

Once the containers are up:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- API docs (Swagger UI): <http://localhost:8000/docs>

## Configuration

### `backend/.env`

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD`, `POSTGRES_DB` | yes | Database credentials for the bundled Postgres container |
| `DATABASE_URL` | yes | SQLAlchemy connection string |
| `ENVIRONMENT` | yes | `development`, `staging`, or `production` |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | yes (for song search & playback) | Spotify Web API app credentials |
| `SPOTIFY_REDIRECT_URI` | yes | Must match the redirect URI registered in your Spotify app |
| `APPLE_MUSIC_TEAM_ID`, `APPLE_MUSIC_KEY_ID`, `APPLE_MUSIC_PRIVATE_KEY` | optional | Enables Apple Music; leave unset to disable the Apple Music endpoints |

### `frontend/.env`

| Variable | Purpose |
|---|---|
| `PUBLIC_API_URL` | Backend HTTP base URL |
| `PUBLIC_WS_URL` | Backend WebSocket base URL |
| `ENVIRONMENT` | `development` / `staging` / `production` |

## Make Targets

Run `make help` for the full list. The most common targets:

| Target | Description |
|---|---|
| `make run` | Build images, start API + frontend + DB, apply migrations, tail logs |
| `make rebuild` | `--no-cache` rebuild + restart |
| `make run-backend` / `make run-frontend` | Start a single side independently |
| `make migrate` / `make migrate-make M="msg"` / `make migrate-down` / `make migrate-reset` | Alembic operations |
| `make test` | Unit + integration tests (excludes system) |
| `make test-cov` | Tests with coverage report (fails under 80 %) |
| `make test-system` | End-to-end Playwright suite via `compose.system.yaml` |
| `make test-load` | k6 capacity test (100 concurrent users → WUN-87) |
| `make test-scalability` / `make test-scalability-server` | k6 scalability test (2,500 users → WUN-88) |
| `make lint` / `make format` / `make type-check` | Ruff lint, Ruff format, mypy |
| `make verify-confidentiality` | Automated security audit (→ WUN-95) |
| `make verify-recoverability` | Crash + restore timing test (→ WUN-90) |
| `make verify-responsive` | Cross-browser responsive layout check (→ WUN-91) |
| `make check-modular` | Verifies backend and frontend can each boot independently |
| `make check-health` | Curl the `/health` endpoint |
| `make shell` | Open a Python REPL inside the API container |
| `make clean` | Stop containers and remove build artifacts |

## API Surface

### HTTP Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/create_room` | Create a new room (host) |
| `POST` | `/join_room` | Join a room by join code |
| `POST` | `/leave_room` | Leave a room |
| `POST` | `/delete_room` | Host-only room deletion |
| `POST` | `/rooms/availability` | Check whether a join code is reachable |
| `GET` | `/rooms/{room_id}/search?q=` | Track search via the room's configured provider |
| `GET` | `/auth/spotify/login` | Start Spotify OAuth flow |
| `GET` | `/auth/spotify/callback` | OAuth redirect target (Spotify) |
| `GET` | `/auth/spotify/token` | Fetch the current user's Spotify access token (refreshes if needed) |
| `GET` | `/auth/apple-music/developer-token` | Mint a MusicKit developer token |
| `POST` | `/auth/apple-music/link` | Link an Apple Music user token to the account |
| `GET` | `/auth/apple-music/token` | Fetch a user music token |
| `GET` | `/auth/apple-music/profile` | Return linked Apple Music profile |
| `GET` | `/health` | Liveness probe |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | Auto-generated API documentation |

Debug endpoints (e.g. `POST /seed_user`) are only registered when `ENVIRONMENT` is `development` / `staging` or `ENABLE_DEBUG_ROUTES=true`.

### WebSocket

`ws://<api>/ws/{room_id}` carries all real-time interactions. Event types are registered in `backend/python/api/event_handlers.py`:

| Event | Description |
|---|---|
| `identify` | Initial handshake; associates the socket with a user |
| `addqueue` | Add a track to the room queue |
| `remove_queue_entry` | Remove an entry from the queue |
| `vote` | Up / down / neutral vote on a queue entry |
| `playback` | Host pause / resume / skip |
| `position_sync` | Periodic playback-position broadcast |
| `history` | Append to playback history |
| `rename` | Rename a room (host) |
| `leave` | Member leaves the room |
| `host_transfer_initiate` / `_accept` / `_reject` | Host-transfer handshake |

Authoritative room state is rebuilt from PostgreSQL on reconnect, so a member who refreshes always rejoins a consistent room.

## Testing

The test pyramid is split across three pytest markers and one E2E suite:

- **Unit tests** (`tests/unit/`): fast, no I/O. Run with `make test`.
- **Integration tests** (`tests/integration/`): spin up Postgres via testcontainers (Docker required).
- **System tests** (`tests/system/`): Playwright-driven E2E. See `backend/python/tests/system/README.md`. Run with `make test-system`.
- **Load tests** (`load-tests/`): k6 capacity and scalability suites.

CI runs all suites on every push (see `.gitlab-ci.yml`).

## Non-Functional Requirement Verification

| NFR | Requirement | How it's met / measured | Verify locally |
|---|---|---|---|
| **WUN-87** | Minimum capacity (100 concurrent users) | k6 stress test (`load-tests/stress_test.js`) | `make test-load` |
| **WUN-88** | Scalability (2,500 concurrent users) | k6 + resource monitoring | `make test-scalability` |
| **WUN-90** | Recoverability | Scripted crash + restore timing | `make verify-recoverability` |
| **WUN-91** | Responsive design | Cross-browser viewport tests via Playwright | `make verify-responsive` |
| **WUN-95** | Confidentiality | TLS 1.2+ (Caddy), OAuth-only credentials (no internal passwords), `bcrypt` for transient secrets, LUKS at rest | `make verify-confidentiality` |

### WUN-95 implementation notes

The system stores no internal passwords; authentication is delegated entirely to Spotify (OAuth 2.0) and Apple Music (MusicKit). The relevant code paths are:

- `backend/python/api/routers/spotify_auth.py`: full OAuth code-flow with signed-state replay protection.
- `backend/python/api/routers/apple_music_auth.py`: MusicKit user-token linking.
- `backend/python/core/security.py`: bcrypt helpers used for transient-token hashing.
- `Caddyfile`: TLS termination with modern cipher suites.

## Deployment

Deployments are driven by GitLab CI (`.gitlab-ci.yml`):

- Push to `dev` → automatic deploy to **staging** (`compose.staging.yaml`).
- Push to `main` → automatic deploy to **production** (`compose.prod.yaml`).

Each deploy job runs `alembic upgrade head` before swapping containers. See `DEPLOYMENT.md` for the host-side runbook (registry login, environment files, secrets).

## License

Prosperity Public License 3.0.0, free for personal and non-commercial use. See `LICENSE.md` or <https://prosperitylicense.com>.
