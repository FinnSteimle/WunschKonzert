# WunschKonzert

WunschKonzert is a collaborative music room application that allows users to join rooms, suggest songs, and vote on what to hear next. It features a real-time synchronized playback experience across all participants.

## Quick Start

The easiest way to get the entire project running is using Docker and the provided Makefile.

1. Clone the repository:
```bash
git clone https://gitlab.ost.ch/SEProj/2026-FS/g15-wunschkonzert/wunschkonzert.git
cd wunschkonzert
```

2. Start everything (Backend, Frontend, and Database):
```bash
make run
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

## Project Architecture

WunschKonzert follows a modern full-stack architecture:

- Frontend: Built with Svelte 5 and SvelteKit, utilizing TailwindCSS 4 and shadcn-svelte for the UI.
- Backend: A high-performance FastAPI service written in Python 3.14+, using SQLAlchemy (async) for persistence and WebSockets for real-time room synchronization.
- Database: PostgreSQL managed via Alembic migrations.
- Infrastructure: Fully containerized with Docker and Docker Compose.

## Project Structure

```text
.
├── backend/            # Python FastAPI service
│   ├── python/         # Source code, models, and migrations
│   └── tests/          # Pytest suite
├── frontend/           # SvelteKit application
│   ├── src/            # Svelte components and logic
│   └── static/         # Static assets
├── scripts/            # Utility scripts (e.g., CI/CD checks)
├── Makefile            # Root automation for dev workflows
└── compose.yaml        # Docker orchestration
```

## Development Commands

The root Makefile provides several commands to manage the project:

| Command | Description |
|---------|-------------|
| `make run` | Build and start all services (API + Frontend + DB) |
| `make install` | Build and start containers in the background |
| `make test` | Run backend unit tests |
| `make lint` | Run backend linter (Ruff) |
| `make format` | Format backend code |
| `make migrate` | Apply database migrations |
| `make clean` | Stop containers and remove build artifacts |
| `make verify-responsive` | Run cross-browser responsive tests (NFR WUN-91) |
| `make verify-recoverability` | Run recoverability crash tests (NFR WUN-90) |
| `make verify-confidentiality` | Run automated security audit (NFR WUN-95) |

## Non-Functional Requirement (NFR) Verification

The project includes specialized commands to verify compliance with Non-Functional Requirements. These commands use isolated environments and automated checks:

- **Responsive Design (WUN-91):** Run `make verify-responsive`. This executes tests across Chromium, Firefox, and WebKit engines at both mobile and desktop resolutions.
- **Recoverability (WUN-90):** Run `make verify-recoverability`. This simulates a service crash and measures restoration time.
- **Confidentiality (WUN-95):** Run `make verify-confidentiality`. This performs a security audit of the configuration and data handling.

## Frontend MVP Setup

```bash
cd frontend
cp .env.example .env
```

2. Configure backend Spotify credentials (required for song search):

```bash
cd backend
cp .env.example .env
# set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
```

3. Start services (recommended):

```bash
make run
```

4. MVP routes:

- Landing: `http://localhost:5173/`
- Create room: `http://localhost:5173/create`
- Join by link: `http://localhost:5173/join/{ROOM_CODE}`
- Room page: `http://localhost:5173/room/{ROOM_CODE}`

## Minimal backend adjustments made

The backend was extended minimally to support required frontend MVP flows while preserving existing routes and payloads:

- Added room lifecycle/state endpoints:
  - `POST /delete_room` (host-only room deletion)
  - `GET /rooms/{room_id}/state` (authoritative room snapshot, DB-backed recovery)
- Added queue/vote/playback/search support for MVP:
  - `POST /rooms/{room_id}/queue` (add song to queue)
  - `POST /rooms/{room_id}/queue/{queue_entry_id}/vote` (upvote/downvote/neutral)
  - `POST /rooms/{room_id}/playback` (host pause/resume)
  - `GET /rooms/{room_id}/search?q=` (Spotify track search)
- Extended `/ws/{room_id}` handling for MVP events (`addqueue`, `vote`, `playback`, `leave`) and broadcasts updated room state.
- Added DB-backed room-state rehydration logic so rooms/queue/votes/playback state can be rebuilt from PostgreSQL after restart.
- Kept existing endpoints (`/create_room`, `/join_room`, `/leave_room`, `/add_music_provider`, `/ws/{room_id}`) intact and backward-compatible.

## Testing

We prioritize code quality through automated testing:

- Backend: Run `make test` to execute the Python test suite.
- Frontend: Navigate to `frontend/` and run `npm test` or `npm run test:unit`.
- Integration: Automated checks ensure services can run independently and together.

## License

This project is licensed under the Prosperity License 3.0.0. This means you are free to use the software for personal and non-commercial purposes. For more details, see [https://prosperitylicense.com/](https://prosperitylicense.com/).