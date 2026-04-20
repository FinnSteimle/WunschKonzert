from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

import repositories.oauth_state_repo as oauth_state_repo


def _base64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64_url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def build_signed_state(
    *,
    secret: str,
    user_id: str,
    return_to: str,
    nonce: str,
    issued_at: int,
) -> str:
    payload = {
        "user_id": user_id,
        "return_to": return_to,
        "nonce": nonce,
        "issued_at": issued_at,
    }
    payload_b64 = _base64_url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _base64_url_encode(
        hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    return f"{payload_b64}.{signature}"


def parse_signed_state(
    *,
    state: str,
    secret: str,
    ttl_seconds: int,
) -> dict[str, str | int] | None:
    if "." not in state:
        return None
    payload_b64, signature = state.split(".", 1)
    expected_signature = _base64_url_encode(
        hmac.new(
            secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_base64_url_decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, binascii.Error):
        return None

    user_id = payload.get("user_id")
    return_to = payload.get("return_to")
    nonce = payload.get("nonce")
    issued_at = payload.get("issued_at")
    if not isinstance(user_id, str) or not isinstance(return_to, str):
        return None
    if not isinstance(nonce, str) or not nonce:
        return None
    if not isinstance(issued_at, int):
        return None

    now_ts = int(datetime.now(UTC).timestamp())
    if issued_at > now_ts + 60:
        return None
    if now_ts - issued_at > ttl_seconds:
        return None
    return payload


async def issue_state(
    *,
    provider_id: str,
    secret: str,
    user_id: str,
    return_to: str,
    ttl_seconds: int,
) -> str:
    now = datetime.now(UTC)
    nonce = secrets.token_urlsafe(32)
    state = build_signed_state(
        secret=secret,
        user_id=user_id,
        return_to=return_to,
        nonce=nonce,
        issued_at=int(now.timestamp()),
    )
    await oauth_state_repo.create_oauth_state_nonce(
        nonce=nonce,
        provider_id=provider_id,
        issued_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    return state


async def verify_and_consume_state(
    *,
    provider_id: str,
    secret: str,
    state: str,
    ttl_seconds: int,
) -> dict[str, str]:
    payload = parse_signed_state(state=state, secret=secret, ttl_seconds=ttl_seconds)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    nonce = str(payload["nonce"])
    consumed = await oauth_state_repo.consume_oauth_state_nonce(
        nonce=nonce, provider_id=provider_id
    )
    if not consumed:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    return {"user_id": str(payload["user_id"]), "return_to": str(payload["return_to"])}
