import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

import repositories.user_repo as user_repo
from core.database import get_session_factory
from core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
)
from models.domain import (
    AccountStatus,
    MusicProvider,
    PlaybackSession,
    ProviderAccount,
    QueueEntry,
    QueueEntryStatus,
    SongFeedback,
    Track,
)


async def create_music_provider(
    provider_id: str, name: str, session: AsyncSession | None = None
) -> MusicProvider:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            provider = await create_music_provider(
                provider_id, name, session=new_session
            )
            await new_session.commit()
            return provider
    try:
        await get_music_provider(provider_id, session=session)
        raise ResourceExistsError("Provider already exists in database.")
    except ResourceNotFoundError:
        pass

    provider = MusicProvider(providerId=provider_id, name=name)
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return provider


async def get_music_provider(
    provider_id: str, session: AsyncSession | None = None
) -> MusicProvider:
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_music_provider(provider_id, session=new_session)

    provider: MusicProvider | None = await session.get(MusicProvider, provider_id)
    if provider is None:
        raise ResourceNotFoundError("Provider not found in database.")
    return provider


async def create_provider_account(
    user_id: str, provider_id: str, external_user_id: str
) -> ProviderAccount:
    """Create a new provider account for a user"""
    # Check if user exists
    user = await user_repo.get_user(user_id)
    if not user:
        raise ValueError("User not found")

    # Check if provider account already exists for this user and provider
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(
                f"User already has an account linked for provider {provider_id}"
            )

    # Create new provider account
    session_factory = get_session_factory()
    async with session_factory() as session:
        provider_account = ProviderAccount(
            providerAccountId=str(uuid.uuid4()),
            externalUserId=external_user_id,
            userId=user_id,
            providerId=provider_id,
            status=AccountStatus.ACTIVE,
        )
        session.add(provider_account)
        await session.commit()
        await session.refresh(provider_account)
        return provider_account


async def get_queue_entries(room_id: str) -> Sequence[QueueEntry]:
    """Get all queue entries for a room, ordered by position"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
        )
        return result.scalars().all()


async def get_current_playback_session(room_id: str) -> PlaybackSession | None:
    """Get the current playback session for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(PlaybackSession)
            .where(PlaybackSession.roomId == room_id)
            .order_by(PlaybackSession.startedAt.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_track(track_id: str) -> Track | None:
    """Get track by ID or return None if not found"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await session.get(Track, track_id)


async def create_track(track_data: dict[str, object]) -> Track:
    """Create a new track"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        track = Track(**track_data)
        session.add(track)
        await session.commit()
        await session.refresh(track)
        return track


async def create_queue_entry(queue_entry_data: dict[str, object]) -> QueueEntry:
    """Create a new queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        queue_entry = QueueEntry(**queue_entry_data)
        session.add(queue_entry)
        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def get_queue_entry(queue_entry_id: str) -> QueueEntry | None:
    """Get queue entry by ID"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await session.get(QueueEntry, queue_entry_id)


async def update_queue_entry(
    queue_entry_id: str, updates: dict[str, object]
) -> QueueEntry:
    """Update a queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        queue_entry = await session.get(QueueEntry, queue_entry_id)
        if not queue_entry:
            raise ValueError("Queue entry not found")

        for key, value in updates.items():
            setattr(queue_entry, key, value)

        await session.commit()
        await session.refresh(queue_entry)
        return queue_entry


async def get_queue_entry_by_track(room_id: str, track_id: str) -> QueueEntry | None:
    """Get non-played queue entry by room ID and track ID."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry).where(
                QueueEntry.roomId == room_id,
                QueueEntry.trackId == track_id,
                QueueEntry.status != QueueEntryStatus.PLAYED,
            )
        )
        return result.scalar_one_or_none()


async def create_playback_session(playback_data: dict[str, object]) -> PlaybackSession:
    """Create a new playback session"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        playback_session = PlaybackSession(**playback_data)
        session.add(playback_session)
        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def update_playback_session(
    playback_session_id: str, updates: dict[str, object]
) -> PlaybackSession:
    """Update a playback session"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        playback_session = await session.get(PlaybackSession, playback_session_id)
        if not playback_session:
            raise ValueError("Playback session not found")

        for key, value in updates.items():
            setattr(playback_session, key, value)

        await session.commit()
        await session.refresh(playback_session)
        return playback_session


async def get_song_feedback_by_queue_entry(
    queue_entry_id: str,
) -> Sequence[SongFeedback]:
    """Get all song feedback for a queue entry"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
            )
        )
        return result.scalars().all()


async def get_song_feedback(queue_entry_id: str, user_id: str) -> SongFeedback | None:
    """Get song feedback for a user"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(SongFeedback).where(
                SongFeedback.queueEntryId == queue_entry_id,
                SongFeedback.userId == user_id,
            )
        )
        return result.scalar_one_or_none()


async def create_or_update_song_feedback(
    feedback_data: dict[str, object],
) -> SongFeedback:
    """Create or update song feedback"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing = await get_song_feedback(
            str(feedback_data["queueEntryId"]), str(feedback_data["userId"])
        )

        if existing:
            existing = await session.merge(existing)
            for key, value in feedback_data.items():
                setattr(existing, key, value)
            feedback = existing
        else:
            feedback = SongFeedback(**feedback_data)
            session.add(feedback)

        await session.flush()
        await session.refresh(feedback)
        await session.commit()
        return feedback


async def delete_song_feedback(queue_entry_id: str, user_id: str) -> None:
    """Delete song feedback"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        feedback = await get_song_feedback(queue_entry_id, user_id)
        if feedback:
            await session.delete(feedback)
            await session.commit()


async def get_max_queue_position(room_id: str) -> int:
    """Get the maximum queue position for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(func.max(QueueEntry.position)).where(QueueEntry.roomId == room_id)
        )
        max_position = result.scalar_one_or_none()
        return int(max_position or 0)


async def get_playing_queue_entry(room_id: str) -> QueueEntry | None:
    """Get the currently playing queue entry for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(
                QueueEntry.roomId == room_id,
                QueueEntry.status == QueueEntryStatus.PLAYING,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_first_queued_entry(room_id: str) -> QueueEntry | None:
    """Get the first queued entry for a room"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(QueueEntry.roomId == room_id)
            .order_by(QueueEntry.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_provider_account_by_user(
    user_id: str, provider_id: str
) -> ProviderAccount | None:
    """Get a provider account for a user and provider, or None."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        return result.scalar_one_or_none()


async def create_or_update_provider_account_tokens(
    user_id: str,
    provider_id: str,
    external_user_id: str,
    access_token: str,
    refresh_token: str,
    token_expires_at: datetime,
) -> ProviderAccount:
    """Create or update a provider account with OAuth tokens."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(ProviderAccount).where(
                ProviderAccount.userId == user_id,
                ProviderAccount.providerId == provider_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.externalUserId = external_user_id
            existing.accessToken = access_token
            existing.refreshToken = refresh_token
            existing.tokenExpiresAt = token_expires_at
            existing.status = AccountStatus.ACTIVE
            await session.commit()
            await session.refresh(existing)
            return existing

        provider_account = ProviderAccount(
            providerAccountId=str(uuid.uuid4()),
            externalUserId=external_user_id,
            userId=user_id,
            providerId=provider_id,
            status=AccountStatus.ACTIVE,
            accessToken=access_token,
            refreshToken=refresh_token,
            tokenExpiresAt=token_expires_at,
        )
        session.add(provider_account)
        await session.commit()
        await session.refresh(provider_account)
        return provider_account


async def update_provider_account_tokens(
    provider_account_id: str,
    access_token: str,
    token_expires_at: datetime,
    refresh_token: str | None = None,
) -> ProviderAccount:
    """Update OAuth tokens on an existing provider account."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        pa = await session.get(ProviderAccount, provider_account_id)
        if not pa:
            raise ValueError("Provider account not found")
        pa.accessToken = access_token
        pa.tokenExpiresAt = token_expires_at
        if refresh_token is not None:
            pa.refreshToken = refresh_token
        await session.commit()
        await session.refresh(pa)
        return pa


async def get_next_queued_entry(room_id: str) -> QueueEntry | None:
    """Get the next queued entry by highest vote score, then earliest position."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(QueueEntry)
            .where(
                QueueEntry.roomId == room_id,
                QueueEntry.status == QueueEntryStatus.QUEUED,
            )
            .order_by(QueueEntry.voteScore.desc(), QueueEntry.position.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def check_db_health() -> dict[str, object]:
    """Check if database is healthy by executing a simple query"""
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                return {"status": "ok"}
        return {"status": "error", "detail": "Query returned unexpected result"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
