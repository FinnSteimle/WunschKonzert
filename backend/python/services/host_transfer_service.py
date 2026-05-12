from __future__ import annotations

from datetime import UTC, datetime

import services.room_service as room_service

MAX_SYSTEM_MESSAGES = 5


def _time_now() -> str:
    return datetime.now(UTC).isoformat()


def _get_transfer(room_id: str) -> dict[str, object] | None:
    cached = room_service.room_state_cache.get(room_id)
    if not cached:
        return None
    transfer = cached.get("transfer")
    return transfer if isinstance(transfer, dict) else None


def _set_transfer(room_id: str, transfer: dict[str, object] | None) -> None:
    cached = room_service.room_state_cache.get(room_id)
    if cached is None:
        return
    if transfer is None:
        cached.pop("transfer", None)
    else:
        cached["transfer"] = transfer
