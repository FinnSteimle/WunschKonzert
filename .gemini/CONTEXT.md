# Session Context: Wunschkonzert Backend

## What we've mastered
- **core/database.py Architecture:** Singleton Pattern and Lazy Factory.
- **URL "Healing" Logic:** Robust "split-and-rebuild" strategy.
- **The Async Pitfall:** `expire_on_commit=False` for `AsyncSession`.
- **The "Loop Gap" Solution:** Fixed `RuntimeError` and `InterfaceError` by setting `asyncio_default_fixture_loop_scope = "session"` in `pyproject.toml`. This ensures that session-scoped fixtures (like the Database Engine) and function-scoped fixtures (like the Database Session) share the same event loop as the tests.

## Communication Mandate
- **Technical Rigor:** Always prioritize technical rationale, loop/transaction mechanics, and driver-level behavior over analogies or comparisons.
- **Precision:** Direct communication of architectural decisions and errors is required for this project's mentoring style.

## Technical Challenges & Research (Spring 2026)
### 1. Robust CRUD Patterns
We are currently auditing `repositories/crud.py` to ensure consistent handling of:
- **Session Lifecycle:** Ensuring sessions are correctly managed whether they are passed in or created internally.
- **Transaction Boundaries:** Moving `commit()` calls to the outer layer where the session is created, while using `flush()` for intermediate state updates.
- **Error Handling:** Standardizing `ResourceExistsError` and `ResourceNotFoundError` across all domain models.

### 2. Test Coverage Expansion
Expanding `tests/test_crud.py` to cover edge cases, including:
- Room creation and join code collisions.
- Membership status transitions.
- Queue management logic.

## Current State & Strategy
- **Infrastructure:** `testcontainers[postgres]` and `pytest-asyncio` are fully synchronized on a session-scoped event loop.
- **Database:** Using a `session.rollback()` pattern in `conftest.py` for per-test isolation.
- **Next Step:** Refactor `repositories/crud.py` to remove redundant session logic and ensure all functions follow the same "session-aware" pattern.
