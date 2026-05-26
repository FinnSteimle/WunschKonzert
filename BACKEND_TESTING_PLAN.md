# Backend Test Coverage Improvement Plan

## 1. Goal
Increase backend test coverage from the current reported 87% (combined) to >92% while improving test quality, isolation, and edge case handling.

## 2. Strategic Approach

### A. Prioritize Logic-Heavy Unit Tests
Many services and repositories have complex branching logic that is currently only tested via high-level integration tests. We will shift to more granular unit tests using `unittest.mock.AsyncMock` to isolate logic.
- **Repositories:** Specifically target the `if session is None:` branches which are often missed in integration tests (as they use a provided `db_session` fixture).
- **Services:** Mock repository calls to test business logic permutations without database overhead.

### B. Tackle the "Missing" Components
- **API Routers:** Currently have near 0% coverage. We will implement tests using `httpx.AsyncClient` with mocked services to verify endpoint routing, validation, and status code logic.
- **Websockets:** Use `FastAPI.testclient` to simulate websocket connections and verify event broadcasting and handling.

## 3. Targeted Improvements & Edge Cases

### Repositories (Focus: `room_repo`, `membership_repo`, `queue_entry_repo`)
- **Collision Handling:** Unit test the `while True` loops in `room_repo` for `roomId` and `joinCode` collisions by mocking `session.get` and `session.execute` to return a value first, then `None`.
- **Filtering Logic:** Verify that `get_room_with_full_state` correctly handles empty sets and filters out `REMOVED` entries as expected.
- **Error Mapping:** Ensure that low-level SQLAlchemy errors are correctly mapped to domain-specific exceptions (e.g., `ResourceNotFoundError`).

### Services (Focus: `vote_service`, `playback_service`, `host_transfer_service`)
- **Vote Thresholds:** Expand `test_skip_threshold_math` to cover more diverse room sizes and the "neutral" vote transition.
- **Host Transfer Race Conditions:** Test scenarios where the target user leaves the room or the host leaves before a pending transfer is accepted.
- **Rank Math:** Verify `orderRank` calculations in `queue_service` and `vote_service` to ensure stable sorting even with many votes.
- **Playback Synchronization:** Test edge cases where a host's position update is received for a track that was just skipped/finished.

### Providers (Focus: `spotify_client`, `apple_music_client`)
- **API Rate Limiting:** Simulate `429 Too Many Requests` responses from Spotify/Apple Music and verify retry/error handling logic.
- **Token Expiry:** Test automatic token refresh logic during a playback request.

## 4. Execution Plan
1. **Unit Test Expansion (Repos & Services):** Add targeted unit tests to fill the 37% -> 60%+ unit coverage gap.
2. **API Endpoint Testing:** Implement router tests mocking the service layer.
3. **Websocket Protocol Testing:** Add tests for the event-driven websocket logic.
4. **Validation:** Run coverage reports after each phase to ensure we are hitting the targets.

## 5. Quality Metrics
- **No Mocking of Private Methods:** Focus on testing the public API of services/repos.
- **Property-Based Testing (where applicable):** Use diverse inputs for math-heavy logic (like rank calculation).
- **Deterministic Tests:** Avoid any reliance on real-world API calls or local Docker state.
