from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from core.exceptions import ResourceNotFoundError
from models.domain import QueueEntry, QueueEntryStatus


async def get_queue_entries(
    room_id: str, session: AsyncSession | None = None
) -> Sequence[QueueEntry]:
    """Get all queue entries for a room, ordered by position"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_queue_entries(room_id, session=new_session)

    result = await session.execute(
        select(QueueEntry)
        .where(QueueEntry.roomId == room_id)
        .order_by(QueueEntry.position.asc())
    )
    return result.scalars().all()


async def get_queue_entry(
    queue_entry_id: str, session: AsyncSession | None = None
) -> QueueEntry | None:
    """Get queue entry by ID"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_queue_entry(queue_entry_id, session=new_session)

    return await session.get(QueueEntry, queue_entry_id)


async def create_queue_entry(
    queue_entry_data: dict[str, object], session: AsyncSession | None = None
) -> QueueEntry:
    """Create a new queue entry"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            queue_entry = await create_queue_entry(
                queue_entry_data, session=new_session
            )
            await new_session.commit()
            return queue_entry

    queue_entry = QueueEntry(**queue_entry_data)
    session.add(queue_entry)
    await session.flush()
    await session.refresh(queue_entry)
    return queue_entry


async def update_queue_entry(
    queue_entry_id: str,
    updates: dict[str, object],
    session: AsyncSession | None = None,
) -> QueueEntry:
    """Update a queue entry"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            updated_entry = await update_queue_entry(
                queue_entry_id, updates, session=new_session
            )
            await new_session.commit()
            return updated_entry

    queue_entry = await session.get(QueueEntry, queue_entry_id)
    if not queue_entry:
        raise ResourceNotFoundError("Queue entry not found")

    for key, value in updates.items():
        setattr(queue_entry, key, value)

    await session.flush()
    await session.refresh(queue_entry)
    return queue_entry


async def get_queue_entry_by_track(
    room_id: str, track_id: str, session: AsyncSession | None = None
) -> QueueEntry | None:
    """Get non-played queue entry by room ID and track ID."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_queue_entry_by_track(
                room_id, track_id, session=new_session
            )

    result = await session.execute(
        select(QueueEntry).where(
            QueueEntry.roomId == room_id,
            QueueEntry.trackId == track_id,
            QueueEntry.status != QueueEntryStatus.PLAYED,
        )
    )
    return result.scalar_one_or_none()


async def get_max_queue_position(
    room_id: str, session: AsyncSession | None = None
) -> int:
    """Get the maximum queue position for a room"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_max_queue_position(room_id, session=new_session)

    result = await session.execute(
        select(func.max(QueueEntry.position)).where(QueueEntry.roomId == room_id)
    )
    max_position = result.scalar_one_or_none()
    return int(max_position or 0)


async def get_playing_queue_entry(
    room_id: str, session: AsyncSession | None = None
) -> QueueEntry | None:
    """Get the currently playing queue entry for a room"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_playing_queue_entry(room_id, session=new_session)

    result = await session.execute(
        select(QueueEntry)
        .where(
            QueueEntry.roomId == room_id,
            QueueEntry.status == QueueEntryStatus.PLAYING,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_first_queued_entry(
    room_id: str, session: AsyncSession | None = None
) -> QueueEntry | None:
    """Get the first queued entry for a room"""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_first_queued_entry(room_id, session=new_session)

    result = await session.execute(
        select(QueueEntry)
        .where(QueueEntry.roomId == room_id)
        .order_by(QueueEntry.position.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_queued_entry(
    room_id: str, session: AsyncSession | None = None
) -> QueueEntry | None:
    """Get the next queued entry by highest vote score, then earliest position."""
    if session is None:
        session_factory = get_session_factory()
        async with session_factory() as new_session:
            return await get_next_queued_entry(room_id, session=new_session)

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
