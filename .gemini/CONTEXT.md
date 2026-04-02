# Session Context: Wunschkonzert Backend

## Core Achievements
- **core/database.py Architecture:** Implemented a Singleton Pattern with a Lazy Factory for robust session management.
- **URL "Healing" Logic:** Developed a "split-and-rebuild" strategy to handle inconsistent database connection strings.
- **The Async Pitfall:** Configured `expire_on_commit=False` for `AsyncSession` to prevent accidental synchronous lookups.
- **The "Loop Gap" Solution:** Resolved `RuntimeError` and `InterfaceError` by synchronizing `asyncio_default_fixture_loop_scope` and `test_loop_scope` to `"session"` in `pyproject.toml`. This ensures that session-scoped fixtures and function-scoped sessions share the same event loop.

## Communication Mandate
- **Technical Rigor:** Always prioritize technical rationale, loop/transaction mechanics, and driver-level behavior over analogies.
- **Precision:** Maintain direct communication of architectural decisions and errors; no filler.

## The Mission: Refactor `repositories/crud.py`
The objective is to ensure all CRUD functions are fully "Session-Aware" and follow consistent transactional patterns.

- **Task 1: Update `get_room` to accept an optional session.**
  - Ensure it follows the recursive pattern: if no session is provided, create one; otherwise, use the existing one.
- **Task 2: Update `create_room` to use the `commit-on-new / flush-on-existing` pattern.**
  - Call `commit()` only when the function instantiates its own session.
  - Use `flush()` when an existing session is passed in to allow the caller to control the transaction.
- **Task 3: Write the Join Code Collision test in `tests/test_crud.py` using mocks.**
  - Use `unittest.mock` to mock `_generate_join_code` to force and verify the collision-handling `while` loop logic.

## Technical Challenges & Research
### 1. Robust CRUD Patterns
We are currently auditing `repositories/crud.py` to ensure consistent handling of:
- **Session Lifecycle:** Managing sessions across service and repository layers.
- **Transaction Boundaries:** Moving `commit()` calls to the outer layer where the session is created, while using `flush()` for intermediate state updates.
- **Error Handling:** Standardizing `ResourceExistsError` and `ResourceNotFoundError` across all domain models.

### 2. Test Coverage Expansion
Expanding `tests/test_crud.py` to cover critical edge cases:
- Room creation and join code collisions.
- Membership status transitions.
- Queue management and playback logic.

## Current State & Strategy
- **Infrastructure:** `testcontainers[postgres]` and `pytest-asyncio` are synchronized on a session-scoped event loop.
- **Database:** Using a `session.rollback()` pattern in `conftest.py` for per-test isolation.
- **Next Step:** Begin the refactor of `repositories/crud.py` starting with `get_room` and `create_room`.
