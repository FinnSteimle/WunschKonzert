# Wunschkonzert Backend

A FastAPI-based collaborative music room backend built with async/await and WebSocket support.

## Overview

Wunschkonzert Backend provides real-time room management, user authentication, and collaborative music queue functionality. It uses:

- **FastAPI** - Modern web framework for building APIs
- **SQLAlchemy** - ORM for database operations
- **AsyncPG** - Async PostgreSQL driver
- **Alembic** - Database migrations
- **Docker** - Containerized deployment

## Project Structure

```
backend/python/
├── main.py                 # Application entry point
├── fast_api.py             # FastAPI app setup and routes
├── database.py             # SQLAlchemy models and ORM definitions
├── db_utils.py             # Database utility functions
├── models.py               # Pydantic request/response models
├── migrations/             # Alembic database migrations
├── tests/                  # Test suite
│   ├── test_fast_api.py
│   ├── test_integration_placeholder.py
│   └── test_joins.py
├── pyproject.toml          # Project dependencies and configuration
```

## Prerequisites

- Docker and Docker Compose
- Make (optional, but recommended)
- Python 3.14+ (if running locally without Docker)
- PostgreSQL database

## Quick Start

### Using Make (Recommended)

1. **Install and run the backend:**
   ```bash
   make install
   make run
   ```

2. **Apply database migrations:**
   ```bash
   make migrate
   ```

3. **Check API health:**
   ```bash
   make check-health
   ```

The API will be available at `http://localhost:8000`

## Make Targets

### Development

- `make install` - Build Docker containers
- `make run` - Run development server with migrations applied
- `make shell` - Open Python shell in container

### Database

- `make migrate` - Apply all pending migrations
- `make migrate-make M="description"` - Create a new migration
- `make migrate-down` - Rollback last migration
- `make migrate-reset` - Reset all migrations to base

### Code Quality

- `make lint` - Run Ruff linter
- `make format` - Format code with Ruff
- `make type-check` - Run Basedpyright type checking

### Testing

- `make test` - Run unit tests
- `make test-cov` - Run tests with coverage report

### Utilities

- `make check-health` - Check API health endpoint
- `make db-health` - Check database connection
- `make clean` - Stop containers and clean up artifacts

## API Endpoints

### Health Checks

- `GET /health` - Basic health check
- `GET /db-health` - Database health check
- `GET /hello` - Greeting endpoint

### Authentication

- `POST /auth/account` - Account authentication (dummy)
- `POST /auth/user` - User authentication (validates user exists)
- `POST /auth/register` - Register a new user

### Room Management

- `POST /join_room` - Join a room (creates user if not exists)
  ```json
  {
    "room_id": "room_123",
    "user_id": "user_456"
  }
  ```

- `POST /leave_room` - Leave a room (marks membership as inactive)
  ```json
  {
    "room_id": "room_123",
    "user_id": "user_456"
  }
  ```

### WebSocket Endpoints

- `WS /ws/{room_id}` - Room-specific WebSocket connection
  - Sends current room state on connect
  - Broadcasts updated room state on changes

- `WS /ws` - Generic WebSocket connection (echo endpoint)

## Room State Structure

The room state is cached and broadcast to all connected clients:

```json
{
  "members": [
    {
      "user": {
        "userId": "user_123",
        "displayName": "Alice"
      },
      "membership": {
        "joinedAt": "2024-01-15T10:30:45.123456",
        "leftAt": null,
        "membershipStatus": "active"
      }
    },
    {
      "user": {
        "userId": "user_456",
        "displayName": "Bob"
      },
      "membership": {
        "joinedAt": "2024-01-15T10:25:00.000000",
        "leftAt": "2024-01-15T10:35:00.000000",
        "membershipStatus": "inactive"
      }
    }
  ]
}
```

## Database Models

### Identity Package
- **User** - User profile and identity
- **Account** - Account credentials and authentication type
- **MusicProvider** - Music streaming providers
- **ProviderAccount** - User's provider-specific accounts

### Room Management
- **Room** - Collaborative room
- **RoomMembership** - User membership in rooms with status tracking

### Queue and Playback
- **Track** - Music track information
- **QueueEntry** - Song in room queue
- **PlaybackSession** - Current playback state
- **PlaybackHistoryEntry** - Track play history

### Voting System
- **ProposalVoteSession** - Base voting proposal
- **SkipProposal** - Skip song proposal
- **ReplayProposal** - Replay song proposal
- **DeleteQueueEntryProposal** - Delete queue entry proposal
- **KickUserProposal** - Kick user proposal
- **ProposalVote** - Individual vote on proposal

### Interactions
- **Comment** - Comments on queue entries
- **SongFeedback** - User feedback (like/dislike/skip)

## Environment Variables

Required environment variables:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/wunschkonzert
```

## Development Workflow

1. **Start the development server:**
   ```bash
   make run
   ```

2. **Make code changes** - The server will hot-reload

3. **Run tests:**
   ```bash
   make test
   ```

4. **Check code quality:**
   ```bash
   make lint
   make format
   make type-check
   ```

5. **Create a migration** (after model changes):
   ```bash
   make migrate-make M="add user field"
   ```

6. **Apply migrations:**
   ```bash
   make migrate
   ```

## Testing

Run the test suite:

```bash
# Unit tests only
make test

# With coverage report
make test-cov

# Integration tests
docker compose exec -T api uv run pytest -m integration
```

## Common Tasks

### Check if API is running
```bash
make check-health
```

### Check database connection
```bash
make db-health
```

### View logs
```bash
docker compose logs -f api
```

### Open Python shell in container
```bash
make shell
```

### Format and lint code
```bash
make format
make lint
```

### Run type checking
```bash
make type-check
```

## Troubleshooting

### Database connection failed
- Check `DATABASE_URL` is correct
- Verify PostgreSQL is running: `make db-health`
- Check Docker containers: `docker compose ps`

### Port already in use
- Change port in `docker compose.yaml` or kill process on port 8000

### Migrations failing
- Reset migrations: `make migrate-reset`
- Apply fresh migrations: `make migrate`

### Type checking errors
- Run: `make type-check` to see all errors
- Errors are typically false positives and can be ignored with `# type: ignore` comments

## Architecture Notes

### Async Operations
- All database operations are async using SQLAlchemy's async API
- WebSocket connections use FastAPI's async WebSocket handling
- All functions marked with `async def` must be awaited with `await`

### Room State Caching
- Room state is maintained in `room_state_cache` dictionary
- Updates are broadcast to all connected WebSocket clients
- Format follows the structure in `roomStateExample.json`

### Event Handling
- WebSocket messages are processed by `handle_room_events()`
- Currently a dummy implementation - extend to handle specific events
- Updates trigger `send_room_state()` broadcast

## Contributing

1. Follow the existing code style
2. Run type checking and linting before committing
3. Write tests for new features
4. Update migrations if models change
5. Update this README for significant changes

## License

[Add license information here]
