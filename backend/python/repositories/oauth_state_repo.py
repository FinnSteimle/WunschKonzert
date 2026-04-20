from datetime import UTC, datetime

from sqlalchemy import update

from core.database import get_session_factory
from models.domain import OAuthStateNonce


async def create_oauth_state_nonce(
    nonce: str,
    provider_id: str,
    expires_at: datetime,
    issued_at: datetime | None = None,
) -> OAuthStateNonce:
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = OAuthStateNonce(
            nonce=nonce,
            providerId=provider_id,
            issuedAt=issued_at or datetime.now(UTC),
            expiresAt=expires_at,
            consumedAt=None,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def consume_oauth_state_nonce(
    nonce: str,
    provider_id: str,
    now: datetime | None = None,
) -> bool:
    checked_at = now or datetime.now(UTC)
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            update(OAuthStateNonce)
            .where(
                OAuthStateNonce.nonce == nonce,
                OAuthStateNonce.providerId == provider_id,
                OAuthStateNonce.consumedAt.is_(None),
                OAuthStateNonce.expiresAt > checked_at,
            )
            .values(consumedAt=checked_at)
        )
        await session.commit()
        return result.rowcount == 1
