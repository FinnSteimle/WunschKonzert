from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException

_cached_token: str | None = None
_cached_expires_at: datetime | None = None

# Test seam: replace with a zero-arg callable returning a fake token string
_sign: Callable[[], str] | None = None

_TOKEN_LIFETIME_DAYS = 150  # 5 months; Apple max is 6
_REFRESH_BEFORE_DAYS = 7


def _credentials() -> tuple[str, str, str]:
    team_id = os.getenv("APPLE_MUSIC_TEAM_ID", "")
    key_id = os.getenv("APPLE_MUSIC_KEY_ID", "")
    raw_key = os.getenv("APPLE_MUSIC_PRIVATE_KEY", "")
    private_key = raw_key.replace("\\n", "\n")
    if not team_id or not key_id or not private_key:
        raise HTTPException(
            status_code=503,
            detail={"code": "apple_music_not_configured"},
        )
    return team_id, key_id, private_key


def _generate() -> str:
    team_id, key_id, private_key = _credentials()
    now = int(datetime.now(UTC).timestamp())
    exp = now + int(timedelta(days=_TOKEN_LIFETIME_DAYS).total_seconds())
    token: str = jwt.encode(
        {"iss": team_id, "iat": now, "exp": exp},
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )
    return token


async def get_developer_token() -> str:
    global _cached_token, _cached_expires_at

    if _sign is not None:
        return _sign()

    now = datetime.now(UTC)
    if (
        _cached_token is not None
        and _cached_expires_at is not None
        and now < _cached_expires_at - timedelta(days=_REFRESH_BEFORE_DAYS)
    ):
        return _cached_token

    token = _generate()
    _cached_token = token
    _cached_expires_at = now + timedelta(days=_TOKEN_LIFETIME_DAYS)
    return token
