# Session Context: Wunschkonzert Backend

## What we've mastered
- **core/database.py Architecture:** Singleton Pattern and Lazy Factory.
- **URL "Healing" Logic:** Robust "split-and-rebuild" strategy.
- **The Async Pitfall:** `expire_on_commit=False` for `AsyncSession`.

## Where we are now
- **Repositories:** `crud.py` type-safety (Sequence/Row) is understood.
- **Testing:** Environment is verified and healthy (**10 passed**).
- **Current Milestone:** `test_create_and_get_user_base_case` is passing.

## Next Steps
- **Independent Tests:** Implement `test_create_and_get_music_provider`.
- **The Room Puzzle:** Implement `test_create_room` (linking User and MusicProvider).
- **Type Safety:** Fix the `mypy` errors in `services/room_service.py` once CRUD tests are complete.
