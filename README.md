# WunschKonzert

WunschKonzert is a collaborative music room application that allows users to join rooms, suggest songs, and vote on what to hear next. It features a real-time synchronized playback experience across all participants.

## Quick Start

The easiest way to get the entire project running is using Docker and the provided Makefile.

1. Clone the repository:
   git clone https://gitlab.ost.ch/SEProj/2026-FS/g15-wunschkonzert/wunschkonzert.git
   cd wunschkonzert

2. Start everything (Backend, Frontend, and Database):
   make run

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

## Development Commands

The root Makefile provides several commands to manage the project:

| Command | Description |
|---------|-------------|
| make run | Build and start all services (API + Frontend + DB) |
| make install | Build and start containers in the background |
| make test | Run backend unit tests |
| make lint | Run backend linter (Ruff) |
| make format | Format backend code |
| make migrate | Apply database migrations |
| make clean | Stop containers and remove build artifacts |

## Testing

We prioritize code quality through automated testing:

- Backend: Run "make test" to execute the Python test suite.
- Frontend: Navigate to frontend/ and run "npm test" or "npm run test:unit".
- Integration: Automated checks ensure services can run independently and together.

## License

This project is licensed under the Prosperity License 3.0.0. This means you are free to use the software for personal and non-commercial purposes. For more details, see [https://prosperitylicense.com/](https://prosperitylicense.com/).
