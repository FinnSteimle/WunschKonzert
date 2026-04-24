from collections.abc import Sequence

from sqlalchemy import func, select, text

from core.database import get_session_factory
from models.domain import (
    PlaybackSession,
    QueueEntry,
    QueueEntryStatus,
    SongFeedback,
    Track,
)


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
